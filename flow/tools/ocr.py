# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import os

import frappe

from flow.lib.tool import tool

MAX_OCR_CHARS = 60_000


@tool
def ocr_extract(file: str) -> str:
	"""Read a file and return its extracted text: OCR for images and scanned PDF pages,
	table + prose extraction for text-layer PDFs, cell text for Excel, and paragraph text
	for Word documents.

	`file` is a File record's name or file_url — either a file attached to this
	conversation or any other File on the site (e.g. one attached to a Sales Invoice or
	HD Ticket) you have read access to. Use this to (re-)read a specific file on demand
	rather than guessing at its contents.
	"""
	from flow.knowledge.extract import FILE_EXTENSIONS, extract_file

	file_doc = _resolve_file(file)
	if not frappe.has_permission("File", "read", doc=file_doc):
		raise PermissionError(f"No permission to read file {file!r}")

	extension = os.path.splitext(file_doc.file_name or file_doc.file_url or "")[1].lower().lstrip(".")
	if extension not in FILE_EXTENSIONS:
		raise ValueError(f"Unsupported file type: .{extension or '?'}")

	text = extract_file(file_doc)
	if not text:
		raise ValueError("No readable text found in this file.")
	if len(text) > MAX_OCR_CHARS:
		text = text[:MAX_OCR_CHARS] + f"\n\n[Truncated — {len(text)} characters total.]"
	return text


def _resolve_file(file: str):
	if frappe.db.exists("File", file):
		return frappe.get_doc("File", file)
	doc_name = frappe.db.get_value("File", {"file_url": file})
	if not doc_name:
		raise ValueError(f"No File found for {file!r}")
	return frappe.get_doc("File", doc_name)


def sync_ocr_tool() -> None:
	"""Upsert the ocr_extract Flow Tool row. Mirrors flow.tools.builtins.sync_builtin_tools —
	uses db.set_value to bypass the immutability guard in FlowTool.validate."""
	import_path = f"flow.tools.ocr.{ocr_extract.name}"
	if frappe.db.exists("Flow Tool", ocr_extract.name):
		frappe.db.set_value(
			"Flow Tool",
			ocr_extract.name,
			{
				"import_path": import_path,
				"description": ocr_extract.description,
				"requires_confirmation": int(ocr_extract.requires_confirmation),
				"is_system_generated": 1,
			},
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"slug": ocr_extract.name,
				"title": "OCR Extract",
				"type": "Imported",
				"import_path": import_path,
				"description": ocr_extract.description,
				"is_system_generated": 1,
				"requires_confirmation": 0,
			}
		).insert(ignore_permissions=True)
