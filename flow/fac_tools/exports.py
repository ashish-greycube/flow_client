# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any

import frappe

from flow.lib.tool import tool

MAX_EXPORT_LIMIT = 5_000
MAX_FILENAME_LENGTH = 80
STANDARD_FIELDS = frozenset({"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"})


@tool
def export_excel(
	doctype: str,
	filters: dict[str, Any] | None = None,
	fields: list[str] | None = None,
	limit: int = 1_000,
	order_by: str | None = None,
	filename: str | None = None,
) -> dict[str, Any]:
	"""Generate an Excel file from permitted DocType records and give the user a download link.

	Use this when the user asks to export data, download results, or receive an Excel
	spreadsheet. It has the same filters, fields, and ordering semantics as Flow's read
	tool, with a maximum of 5,000 rows. Pass explicit field names for a useful export.

	The workbook is stored as a private Frappe File owned by the current user. After this
	tool succeeds, include the returned `markdown_link` unchanged in the final response.
	Do not merely print the file path: the user must receive the clickable download link.
	"""
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError(f"No permission to read {doctype}")
	frappe.permissions.can_export(doctype, raise_exception=True)

	limit = min(max(int(limit), 1), MAX_EXPORT_LIMIT)
	fields = fields or ["name"]
	meta = frappe.get_meta(doctype)
	_validate_fields(meta, fields)
	rows = frappe.get_list(doctype, filters=filters, fields=fields, limit=limit, order_by=order_by)
	headers = [meta.get_label(field) if meta.get_label(field) != "No Label" else field for field in fields]
	data = [headers, *[[row.get(field) for field in fields] for row in rows]]

	from frappe.utils.file_manager import save_file
	from frappe.utils.xlsxutils import make_xlsx

	workbook = make_xlsx(data, doctype)
	file_doc = save_file(
		f"{_safe_filename(filename or doctype)}.xlsx",
		workbook.getvalue(),
		None,
		None,
		is_private=1,
	)
	return _file_response(file_doc, len(rows))


def _file_response(file_doc, row_count: int) -> dict[str, Any]:
	download_path = file_doc.unique_url
	download_url = frappe.utils.get_url(download_path)
	markdown_link = f"[Download {file_doc.file_name}]({download_url})"
	return {
		"success": True,
		"message": "Excel file created. Show markdown_link to the user as a clickable download link.",
		"file_id": file_doc.name,
		"file_name": file_doc.file_name,
		"file_url": file_doc.file_url,
		"download_path": download_path,
		"download_url": download_url,
		"markdown_link": markdown_link,
		"row_count": row_count,
		"is_private": True,
	}


def _validate_fields(meta, fields: list[str]) -> None:
	allowed = STANDARD_FIELDS | {field.fieldname for field in meta.fields}
	invalid = [field for field in fields if field not in allowed]
	if invalid:
		raise frappe.ValidationError(f"Unknown or unsupported fields for {meta.name}: {', '.join(invalid)}")


def _safe_filename(filename: str) -> str:
	name = filename.strip()
	if name.lower().endswith(".xlsx"):
		name = name[:-5]
	return frappe.scrub(name)[:MAX_FILENAME_LENGTH] or "export"
