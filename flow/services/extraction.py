# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Thin, reusable entry point for "get plain text out of this File" — delegates to
flow.knowledge.extract, which does the actual parsing/OCR. Exists as its own module so
other Frappe apps on this bench have one stable import (`flow.services.extraction`)
instead of reaching into the knowledge package directly."""

from __future__ import annotations


def extract_text(file_doc, *, vision_model: str | None = None) -> str:
	"""Extract plain text from a File doc: local parsers/OCR first (pdfplumber, RapidOCR,
	openpyxl, python-docx, python-pptx, olefile, csv), free. `vision_model` is an optional
	Flow Model name — when local OCR finds nothing on an image or scanned PDF page and the
	model supports vision, it's asked to transcribe the page directly rather than returning
	empty text. Does not touch the database; callers persist the result themselves."""
	from flow.knowledge.extract import extract_file

	return extract_file(file_doc, vision_model=vision_model)
