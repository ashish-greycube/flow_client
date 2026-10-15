# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Several File2ERP uploads combined into one Expense Claim.

When a user uploads several receipts together and chooses "one document for all files",
each file still gets its own Flow File2ERP entry and is extracted on its own (the same
Expense Claim fast path as a single upload); the entries just share a `batch` id. The
claim is assembled from them only at review time:

- header fields: every entry's extraction already carries the uploader's employee,
  company and currency, so the first non-empty value of each field is kept, and the
  remarks are joined, one line per file;
- expense rows: every entry's rows, in upload order, each tagged with its file name.

The claim is only created once every entry in the batch has been extracted, so a
receipt that is still being read, failed, or needs review is never silently left out:
the user retries it, fixes it on its own page, or removes it from the batch.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

# Only Expense Claim combines several files into one document: a claim is many receipts
# by nature, while an invoice, order or payment belongs to one counterparty and number.
COMBINABLE_DOCUMENT_TYPES = ("Expense Claim",)
# Tags each merged expense row with the file it came from; never a real field.
SOURCE_KEY = "file"
ENTRY_FIELDS = [
	"name",
	"file",
	"file_name",
	"status",
	"error",
	"document_type",
	"extracted_fields",
	"extracted_line_items",
	"created_document_type",
	"created_document",
	"modified",
]


def batch_entries(batch: str) -> list[dict[str, Any]]:
	"""The caller's entries in `batch`, in upload order. Scoped to the owner, as the
	File2ERP list is."""
	entries = frappe.get_all(
		"Flow File2ERP",
		filters={"batch": batch, "owner": frappe.session.user},
		fields=ENTRY_FIELDS,
		order_by="creation asc",
	)
	if not entries:
		frappe.throw(_("This combined claim has no files."), frappe.DoesNotExistError)
	return entries


def merge(entries: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
	"""The combined claim's header fields and expense rows from the entries' extractions."""
	fields: dict[str, Any] = {}
	remarks = []
	rows = []
	for entry in entries:
		for key, value in load_json(entry.get("extracted_fields"), {}).items():
			if key == "remark":
				if value:
					remarks.append(f"{entry.get('file_name')}: {value}")
			elif fields.get(key) in (None, ""):
				fields[key] = value
		for row in load_json(entry.get("extracted_line_items"), []):
			if isinstance(row, dict):
				rows.append({SOURCE_KEY: entry.get("file_name"), **row})
	fields["remark"] = "\n".join(remarks)
	return fields, rows


def not_ready(entries: list[dict[str, Any]]) -> list[str]:
	"""Why the claim can't be created yet: one message per entry not cleanly extracted."""
	reasons = {
		"Uploaded": _("{0} has not been read yet."),
		"Processing": _("{0} is still being read."),
		"Needs Review": _("{0} needs review: fix it on its own page or remove it from the claim."),
		"Failed": _("{0} could not be read: retry it or remove it from the claim."),
		"Document Created": _("{0} is already part of a created document."),
	}
	no_rows = _("{0} has no expense rows: fix it on its own page or remove it from the claim.")
	messages = []
	for entry in entries:
		label = entry["file_name"] or entry["name"]
		if entry["status"] in reasons:
			messages.append(reasons[entry["status"]].format(label))
		elif not load_json(entry.get("extracted_line_items"), []):
			# Read, but nothing to claim: it would add nothing to the claim unnoticed.
			messages.append(no_rows.format(label))
	return messages


def create_claim(entries: list[dict[str, Any]], fields: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
	"""Create one Expense Claim from the reviewed header and rows, attach every file and
	link every entry to it. Same result shape as create_document_from_entry."""
	from flow.api.file2erp import _attach_source_file, _link_back_to_entry
	from flow.services import document_creation

	doctype = "Expense Claim"
	rows = [{key: value for key, value in row.items() if key != SOURCE_KEY} for row in rows]
	missing = document_creation.find_missing_mandatory(doctype, fields, rows)
	if not rows:
		missing = [_("at least one expense row"), *missing]
	if missing:
		return {
			"result": {
				"doctype": doctype,
				"created": [],
				"failures": [{"error": _("Missing required field(s): {0}").format(", ".join(missing))}],
			},
			"missing_mandatory": missing,
		}

	result = document_creation.create_from_mapped(doctype, fields, rows)
	if result.get("created"):
		created = result["created"][0]
		for entry in entries:
			doc = frappe.get_doc("Flow File2ERP", entry["name"])
			doc.created_document_type = doctype
			doc.created_document = created
			doc.status = "Document Created"
			doc.save()
			_attach_source_file(doc, doctype, created)
			_link_back_to_entry(doc, doctype, created)
	return {"result": result, "missing_mandatory": []}


def load_json(value: str | None, default):
	try:
		return json.loads(value) if value else default
	except (TypeError, ValueError):
		return default
