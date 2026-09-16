# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Turn a Flow Knowledge Source into plain text, ready for chunking."""

from __future__ import annotations

import csv
import os
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO

import frappe
from frappe import _

TEXT_EXTENSIONS = {"txt", "text", "md", "markdown", "csv", "tsv", "log", "rst", "json", "yaml", "yml"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif"}
FILE_EXTENSIONS = {"pdf", "xls", "xlsx", "docx", "doc", "pptx", "html", "htm"} | TEXT_EXTENSIONS | IMAGE_EXTENSIONS

OCR_DPI = 200
MAX_CSV_TABLE_ROWS = 2000

CHILD_FIELDTYPES = {"Table", "Table MultiSelect"}
HTML_FIELDTYPES = {"Text Editor"}
MARKDOWN_FIELDTYPES = {"Markdown Editor"}

URL_TIMEOUT = 20
MAX_FETCH_BYTES = 10 * 1024 * 1024


@dataclass
class ExtractedDoc:
	text: str
	reference_doctype: str | None = None
	reference_name: str | None = None


def extract(source) -> list[ExtractedDoc]:
	handlers = {
		"Text": _extract_text_source,
		"File": _extract_file_source,
		"URL": _extract_url_source,
		"DocType": _extract_doctype_source,
	}
	handler = handlers.get(source.source_type)
	if handler is None:
		frappe.throw(_("Unsupported source type: {0}").format(source.source_type))
	return handler(source)


def _extract_text_source(source) -> list[ExtractedDoc]:
	return _single((source.content or "").strip())


def _extract_file_source(source) -> list[ExtractedDoc]:
	file_doc = frappe.get_doc("File", {"file_url": source.file})
	return _single(extract_file(file_doc))


def extract_file(file_doc, *, vision_model: str | None = None) -> str:
	"""Extract plain text from a File doc by extension. Usable by any caller that holds a File doc.

	`vision_model` is an optional Flow Model name: when local OCR finds nothing on an image
	or scanned PDF page and the model supports vision, it's asked to transcribe the page
	directly rather than returning empty text. Callers that don't pass it get today's
	behaviour unchanged (local OCR only)."""
	extension = os.path.splitext(file_doc.file_name or file_doc.file_url or "")[1].lower().lstrip(".")
	content = file_doc.get_content()
	if extension not in FILE_EXTENSIONS:
		extension = _sniff_extension(content) or extension
	return _extract_by_extension(content, extension, vision_model=vision_model).strip()


def _extract_url_source(source) -> list[ExtractedDoc]:
	import requests

	url = (source.url or "").strip()
	_validate_public_url(url)
	response = requests.get(
		url, timeout=URL_TIMEOUT, stream=True, headers={"User-Agent": "Flow-Knowledge/1.0"}
	)
	response.raise_for_status()

	raw = _read_capped(response)
	content_type = response.headers.get("Content-Type", "").lower()
	if "application/pdf" in content_type or url.split("?")[0].lower().endswith(".pdf"):
		text = _extract_pdf(raw)
	else:
		text = _extract_html(_as_text(raw))
	return _single(text.strip())


def resolve_content_fields(meta, raw) -> list[str]:
	"""Parse a comma-separated content_fields string and validate each name
	against the doctype's meta (blocks injection via crafted field names)."""
	fields = [f.strip() for f in (raw or "").split(",") if f.strip()]
	if not fields:
		frappe.throw(_("No content fields configured."), title=_("Invalid Source"))

	allowed = {df.fieldname for df in meta.fields} | {"name", "creation", "modified", "owner"}
	unknown = [f for f in fields if f not in allowed]
	if unknown:
		frappe.throw(
			_("Unknown fields for {0}: {1}").format(meta.name, ", ".join(unknown)),
			title=_("Invalid Content Fields"),
		)

	child = [f for f in fields if (df := meta.get_field(f)) and df.fieldtype in CHILD_FIELDTYPES]
	if child:
		frappe.throw(
			_("Child table fields are not supported as content fields: {0}").format(", ".join(child)),
			title=_("Invalid Content Fields"),
		)
	return fields


def _extract_doctype_source(source) -> list[ExtractedDoc]:
	doctype = source.reference_doctype
	meta = frappe.get_meta(doctype)
	fields = resolve_content_fields(meta, source.content_fields)

	rows = frappe.get_all(
		doctype, filters=_parse_filters(source.filters), fields=["name", *fields], limit_page_length=0
	)
	docs = []
	for row in rows:
		text = _row_to_text(row, fields, meta)
		if text:
			docs.append(ExtractedDoc(text=text, reference_doctype=doctype, reference_name=row["name"]))
	return docs


# --- format extractors -------------------------------------------------------


def _extract_by_extension(content, extension: str, vision_model: str | None = None) -> str:
	if extension == "pdf":
		return _extract_pdf(_as_bytes(content), vision_model=vision_model)
	if extension in ("xlsx", "xls"):
		return _extract_xlsx(_as_bytes(content))
	if extension == "docx":
		return _extract_docx(_as_bytes(content))
	if extension == "doc":
		return _extract_doc(_as_bytes(content))
	if extension == "pptx":
		return _extract_pptx(_as_bytes(content))
	if extension in ("csv", "tsv"):
		return _extract_csv(_as_text(content), delimiter="," if extension == "csv" else "\t")
	if extension in ("html", "htm"):
		return _extract_html(_as_text(content))
	if extension in IMAGE_EXTENSIONS:
		return _ocr_image(_as_bytes(content), vision_model=vision_model)
	if extension in TEXT_EXTENSIONS:
		return _as_text(content)
	frappe.throw(_("Unsupported file format: .{0}").format(extension or "?"), title=_("Unsupported Format"))


def _extract_pdf(data: bytes, vision_model: str | None = None) -> str:
	import pdfplumber
	from pdfminer.pdfdocument import PDFPasswordIncorrect

	try:
		with pdfplumber.open(BytesIO(data)) as pdf:
			pages = [_extract_pdf_page(page, vision_model=vision_model) for page in pdf.pages]
	except PDFPasswordIncorrect:
		frappe.throw(_("PDF is password protected and cannot be read."), title=_("Cannot Read PDF"))
	return "\n\n".join(page for page in pages if page)


def _extract_pdf_page(page, vision_model: str | None = None) -> str:
	parts = []

	tables = page.find_tables()
	for table in tables:
		markdown = _table_to_markdown(table.extract())
		if markdown:
			parts.append(markdown)

	body = page
	for table in tables:
		body = body.outside_bbox(table.bbox)
	prose = _clean_pdf_text(body.extract_text() or "")
	if prose:
		parts.append(prose)

	# No text layer → raw scan; OCR the full page. Otherwise OCR every image region
	# individually (logos, stamps, embedded scans). Duplicated text on searchable PDFs
	# is acceptable; missing text is not.
	if page.images and not parts:
		parts.append(_ocr_image(_render_page_png(page), vision_model=vision_model))
	elif page.images:
		for image in page.images:
			text = _ocr_region(page, image, vision_model=vision_model)
			if text:
				parts.append(text)

	return "\n\n".join(part for part in parts if part)


def _table_to_markdown(table) -> str:
	rows = [row for row in (table or []) if row]
	if not rows:
		return ""
	lines = []
	for i, row in enumerate(rows):
		cells = [str(cell or "").replace("\n", " ").replace("|", "\\|").strip() for cell in row]
		lines.append("| " + " | ".join(cells) + " |")
		if i == 0:
			lines.append("| " + " | ".join("---" for _ in cells) + " |")
	return "\n".join(lines)


def _ocr_region(page, image, vision_model: str | None = None) -> str:
	bbox = (
		max(image["x0"], page.bbox[0]),
		max(image["top"], page.bbox[1]),
		min(image["x1"], page.bbox[2]),
		min(image["bottom"], page.bbox[3]),
	)
	if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
		return ""
	return _ocr_image(_render_page_png(page.crop(bbox)), vision_model=vision_model)


def _render_page_png(page) -> bytes:
	buffer = BytesIO()
	page.to_image(resolution=OCR_DPI).original.save(buffer, format="PNG")
	return buffer.getvalue()


_ocr_engine_instance = None


def _ocr_engine():
	"""Lazily initialised singleton — RapidOCR model load is expensive."""
	global _ocr_engine_instance
	if _ocr_engine_instance is None:
		from rapidocr import RapidOCR

		_ocr_engine_instance = RapidOCR()
	return _ocr_engine_instance


def _ocr_image(data: bytes, vision_model: str | None = None) -> str:
	result = _ocr_engine()(data)
	text = "\n".join(result.txts) if result.txts else ""
	if text or not vision_model:
		return text

	from flow.lib.model import supports_vision

	if not supports_vision(vision_model):
		return text
	return _vision_ocr(data, vision_model)


def _vision_ocr(data: bytes, vision_model: str) -> str:
	"""Last-resort OCR for a page/region local OCR couldn't read: ask a vision-capable
	model to transcribe it directly. Only called when RapidOCR returned nothing — never
	replaces local OCR, and never raises (a misconfigured fallback shouldn't fail extraction)."""
	import base64

	from flow.lib.model import Model

	encoded = base64.b64encode(data).decode("ascii")
	messages = [
		{
			"role": "user",
			"content": [
				{
					"type": "text",
					"text": "Transcribe all text visible in this image exactly as it appears, "
					"including any tables as Markdown tables. Reply with the transcription only.",
				},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
			],
		}
	]
	try:
		response = Model(vision_model).chat(messages)
	except Exception:
		return ""
	return (response.content or "").strip()


def _extract_xlsx(data: bytes) -> str:
	import openpyxl

	workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
	try:
		sheets = []
		for worksheet in workbook.worksheets:
			rows = []
			for row in worksheet.iter_rows(values_only=True):
				cells = [str(cell) for cell in row if cell is not None]
				if cells:
					rows.append("\t".join(cells))
			if rows:
				sheets.append("# {0}\n{1}".format(worksheet.title, "\n".join(rows)))
		return "\n\n".join(sheets)
	finally:
		workbook.close()


def _extract_docx(data: bytes) -> str:
	from docx import Document
	from docx.table import Table
	from docx.text.paragraph import Paragraph

	document = Document(BytesIO(data))
	parts = []
	for block in document.iter_inner_content():
		if isinstance(block, Paragraph):
			text = block.text.strip()
			if text:
				parts.append(text)
		elif isinstance(block, Table):
			markdown = _table_to_markdown([[cell.text for cell in row.cells] for row in block.rows])
			if markdown:
				parts.append(markdown)
	return "\n\n".join(parts)


def _extract_csv(text: str, delimiter: str) -> str:
	"""Structure CSV/TSV as a Markdown table so line items read like any other tabular
	extraction. Falls back to the raw text for very large files — building a markdown
	table for thousands of rows would blow up the token budget for no benefit."""
	rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
	if not rows or len(rows) > MAX_CSV_TABLE_ROWS:
		return text
	return _table_to_markdown(rows) or text


def _extract_pptx(data: bytes) -> str:
	from pptx import Presentation

	presentation = Presentation(BytesIO(data))
	slides = []
	for index, slide in enumerate(presentation.slides, start=1):
		parts = []
		for shape in slide.shapes:
			if shape.has_text_frame:
				text = "\n".join(p.text for p in shape.text_frame.paragraphs if p.text.strip())
				if text:
					parts.append(text)
			elif shape.has_table:
				rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
				markdown = _table_to_markdown(rows)
				if markdown:
					parts.append(markdown)
		if parts:
			slides.append("# Slide {0}\n{1}".format(index, "\n\n".join(parts)))
	return "\n\n".join(slides)


def _extract_doc(data: bytes) -> str:
	"""Legacy binary .doc has no maintained pure-Python parser (unlike .docx's OOXML).
	Pull the WordDocument stream out of the OLE2 container and keep runs of printable
	characters — a best-effort scrape, not a full reader. The stream also holds any
	embedded objects (images, OLE packages) byte-for-byte, and their binary happens to
	contain plenty of printable-looking runs, so _looks_like_prose filters those out
	rather than feeding the model garbage."""
	import olefile

	# `data=` (not the positional/deprecated bytes form) is required — olefile treats a
	# bytes argument shorter than 1536 bytes as a filename to open, not file content.
	if not olefile.isOleFile(data=data):
		frappe.throw(_("File is not a valid .doc document."), title=_("Cannot Read Document"))

	with olefile.OleFileIO(BytesIO(data)) as ole:
		if not ole.exists("WordDocument"):
			frappe.throw(_("File is not a valid .doc document."), title=_("Cannot Read Document"))
		stream = ole.openstream("WordDocument").read()

	runs = re.findall(rb"[\x09\x0a\x0d\x20-\x7e]{4,}", stream)
	prose = [r.decode("ascii", errors="ignore") for r in runs]
	prose = [r for r in prose if _looks_like_prose(r)]
	return re.sub(r"\n{3,}", "\n\n", "\n".join(prose)).strip()


def _looks_like_prose(run: str) -> bool:
	"""True for a run that reads like natural-language text rather than binary noise
	that happened to fall in the printable ASCII range."""
	if len(run) < 8 or run.count(" ") < 2:
		return False
	wordlike = sum(c.isalpha() or c == " " for c in run)
	return wordlike / len(run) > 0.75


def _extract_html(markup: str) -> str:
	from bs4 import BeautifulSoup

	soup = BeautifulSoup(markup, "lxml")
	for tag in soup(["script", "style", "noscript"]):
		tag.decompose()
	return soup.get_text(separator=" ", strip=True)


# --- helpers -----------------------------------------------------------------


def _single(text: str) -> list[ExtractedDoc]:
	return [ExtractedDoc(text=text)] if text else []


def _sniff_extension(content) -> str | None:
	"""Best-effort magic-byte detection for a file with a missing or wrong extension.
	Only ever returns a format `_extract_by_extension` already knows how to handle —
	never guesses into an unsupported one."""
	if not isinstance(content, (bytes, bytearray)):
		return "txt"

	signatures = (
		(b"%PDF", "pdf"),
		(b"\x89PNG\r\n\x1a\n", "png"),
		(b"\xff\xd8\xff", "jpg"),
		(b"GIF87a", "gif"),
		(b"GIF89a", "gif"),
		(b"BM", "bmp"),
		(b"II*\x00", "tiff"),
		(b"MM\x00*", "tiff"),
	)
	for magic, extension in signatures:
		if content.startswith(magic):
			return extension

	import olefile

	if olefile.isOleFile(data=content):
		return "doc"

	if content[:4] == b"PK\x03\x04":
		try:
			with zipfile.ZipFile(BytesIO(content)) as archive:
				names = archive.namelist()
		except zipfile.BadZipFile:
			return None
		if any(name.startswith("word/") for name in names):
			return "docx"
		if any(name.startswith("xl/") for name in names):
			return "xlsx"
		if any(name.startswith("ppt/") for name in names):
			return "pptx"
		return None

	try:
		content.decode("utf-8")
		return "txt"
	except UnicodeDecodeError:
		return None


def _as_bytes(content) -> bytes:
	return content if isinstance(content, bytes) else content.encode("utf-8", "replace")


def _as_text(content) -> str:
	if isinstance(content, str):
		return content
	import chardet

	encoding = (chardet.detect(content) or {}).get("encoding") or "utf-8"
	return content.decode(encoding, errors="replace")


def _clean_pdf_text(text: str) -> str:
	"""Join single newlines (line-break artifacts) while keeping paragraph breaks."""
	text = re.sub(r"(?<!\n)[ \t]*\n[ \t]*(?!\n)", " ", text)
	text = re.sub(r"[ \t]{2,}", " ", text)
	return text.strip()


def _parse_filters(raw) -> dict:
	if not raw:
		return {}
	import json

	try:
		parsed = json.loads(raw)
	except (TypeError, ValueError):
		frappe.throw(_("Filters must be valid JSON."), title=_("Invalid Filters"))
	if not isinstance(parsed, dict):
		frappe.throw(_("Filters must be a JSON object."), title=_("Invalid Filters"))
	return parsed


def _row_to_text(row: dict, fields: list[str], meta) -> str:
	from frappe.utils import cstr

	lines = []
	for fieldname in fields:
		value = row.get(fieldname)
		if value in (None, ""):
			continue
		df = meta.get_field(fieldname)
		text = _render_rich_text(df, cstr(value))
		if not text:
			continue
		label = df.label if df else fieldname
		lines.append(f"{label}: {text}")
	return "\n".join(lines)


def _render_rich_text(df, value: str) -> str:
	"""Strip HTML/Markdown markup to plain text; pass other fieldtypes through unchanged."""
	if not df:
		return value
	if df.fieldtype in HTML_FIELDTYPES:
		return _extract_html(value)
	if df.fieldtype in MARKDOWN_FIELDTYPES or (df.fieldtype == "Code" and df.options == "Markdown"):
		from frappe.utils import md_to_html

		return _extract_html(md_to_html(value))
	return value


def _validate_public_url(url: str) -> None:
	"""Block non-http(s) schemes and hosts that resolve to internal addresses (SSRF)."""
	import ipaddress
	import socket
	from urllib.parse import urlparse

	parsed = urlparse(url)
	if parsed.scheme not in ("http", "https"):
		frappe.throw(_("URL must use http or https."), title=_("Invalid URL"))
	if not parsed.hostname:
		frappe.throw(_("URL has no host."), title=_("Invalid URL"))

	try:
		infos = socket.getaddrinfo(parsed.hostname, None)
	except socket.gaierror:
		frappe.throw(_("Could not resolve URL host."), title=_("Invalid URL"))

	for info in infos:
		ip = ipaddress.ip_address(info[4][0])
		if (
			ip.is_private
			or ip.is_loopback
			or ip.is_link_local
			or ip.is_reserved
			or ip.is_multicast
			or ip.is_unspecified
		):
			frappe.throw(_("URL resolves to a non-public address."), title=_("Blocked URL"))


def _read_capped(response) -> bytes:
	chunks = []
	total = 0
	for chunk in response.iter_content(8192):
		total += len(chunk)
		if total > MAX_FETCH_BYTES:
			frappe.throw(_("Remote file exceeds the size limit."), title=_("File Too Large"))
		chunks.append(chunk)
	return b"".join(chunks)
