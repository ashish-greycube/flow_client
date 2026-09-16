# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import Any

import frappe

from flow.lib.tool import tool


@tool
def get_file2erp_data(file: str) -> dict[str, Any]:
	"""Look up the File2ERP entry for an already-processed file, if one exists: the
	detected document type, parent fields, and line items a person has already reviewed
	and corrected.

	`file` is a File record's name or file_url — the same identifier you already see for
	attached files. Use this before create/update whenever the user is working from a
	file that has been through File2ERP; it returns validated values instead of noisy raw
	OCR text, and costs nothing to call since no re-extraction happens. Returns
	found=False if no File2ERP entry exists yet for this file — fall back to ocr_extract.
	"""
	file_doc = _resolve_file(file)
	if not frappe.has_permission("File", "read", doc=file_doc):
		raise PermissionError(f"No permission to read file {file!r}")

	name = frappe.db.get_value("Flow File2ERP", {"file": file_doc.name}, "name")
	if not name:
		return {"found": False}

	doc = frappe.get_doc("Flow File2ERP", name)
	if not frappe.has_permission("Flow File2ERP", "read", doc=doc):
		raise PermissionError(f"No permission to read Flow File2ERP {name!r}")

	import json

	return {
		"found": True,
		"file2erp": doc.name,
		"status": doc.status,
		"detected_doctype": doc.detected_doctype,
		"confidence": doc.confidence,
		"fields": json.loads(doc.extracted_fields) if doc.extracted_fields else {},
		"line_items": json.loads(doc.extracted_line_items) if doc.extracted_line_items else [],
	}


def _resolve_file(file: str):
	if frappe.db.exists("File", file):
		return frappe.get_doc("File", file)
	doc_name = frappe.db.get_value("File", {"file_url": file})
	if not doc_name:
		raise ValueError(f"No File found for {file!r}")
	return frappe.get_doc("File", doc_name)


# The tool's slug before the flow.tools.file_box -> flow.tools.file2erp rename. A site
# that had already synced the OCR Agent carries a "get_file_box_data" Flow Tool row
# whose import_path now points at a module that no longer exists; the row itself can
# never be deleted or renamed (system-generated Flow Tool rows are protected — see
# flow.utils.system_generated.block_delete/block_rename, both unconditional for Flow
# Tool), so any agent still listing it fails to load its entire tool set until the
# row's import_path is repointed.
LEGACY_SLUG = "get_file_box_data"


def sync_file2erp_tool() -> None:
	"""Upsert the get_file2erp_data Flow Tool row, and repair the pre-rename
	get_file_box_data row in place if this site still has one. Mirrors
	flow.tools.ocr.sync_ocr_tool — uses db.set_value to bypass the immutability guard
	in FlowTool.validate."""
	_repair_legacy_tool()

	import_path = f"flow.tools.file2erp.{get_file2erp_data.name}"
	if frappe.db.exists("Flow Tool", get_file2erp_data.name):
		frappe.db.set_value(
			"Flow Tool",
			get_file2erp_data.name,
			{
				"import_path": import_path,
				"description": get_file2erp_data.description,
				"requires_confirmation": int(get_file2erp_data.requires_confirmation),
				"is_system_generated": 1,
			},
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"slug": get_file2erp_data.name,
				"title": "Get File2ERP Data",
				"type": "Imported",
				"import_path": import_path,
				"description": get_file2erp_data.description,
				"is_system_generated": 1,
				"requires_confirmation": 0,
			}
		).insert(ignore_permissions=True)


def _repair_legacy_tool() -> None:
	"""Repoint the pre-rename get_file_box_data Flow Tool row at the current module
	instead of leaving it permanently broken. Safe to leave both rows resolvable: the
	runtime tool name an agent sees always comes from the Flow Tool row's own `slug`
	(flow.lib.resolver._build_tool), not from the Python Tool object's name — so
	get_file_box_data and get_file2erp_data can both point at the same function
	without conflict, and an agent that still lists the old slug keeps working."""
	if not frappe.db.exists("Flow Tool", LEGACY_SLUG):
		return
	frappe.db.set_value(
		"Flow Tool",
		LEGACY_SLUG,
		{
			"import_path": f"flow.tools.file2erp.{get_file2erp_data.name}",
			"description": get_file2erp_data.description,
			"is_system_generated": 1,
		},
	)
