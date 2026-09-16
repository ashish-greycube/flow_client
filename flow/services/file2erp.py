# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Background job wired to flow.api.file2erp.start_extraction: extract -> structure ->
save. Idempotent by default — a no-op if the row already has extracted content, so
reopening an entry (or its chat) never re-runs extraction — unless `force=True` (the
entry's "Re-extract Data" action), which always redoes the full pipeline from scratch.
Deliberately NOT wired to after_insert anymore: extraction is scoped to Flow
File2ERP.document_type, so it can't start until the user has picked (or confirmed)
that DocType — see start_extraction."""

from __future__ import annotations

import json

import frappe

from flow.services import extraction, field_mapping, structuring


def process_entry(name: str, force: bool = False) -> None:
	doc = frappe.get_doc("Flow File2ERP", name)
	if not force and (doc.raw_text or doc.extracted_fields):
		return

	doc.db_set("status", "Processing", update_modified=False, commit=True)

	try:
		file_doc = frappe.get_doc("File", doc.file)
		settings = frappe.get_cached_doc("Flow File2ERP Settings")
		model_name = settings.extraction_model or None
		vision_model = model_name if model_name and _supports_vision(model_name) else None

		text = extraction.extract_text(file_doc, vision_model=vision_model)
		if not text:
			# update_modified defaults True here (unlike the "Processing" ping above): the
			# frontend's editable-table components only re-sync from the server when the
			# entry's `modified` timestamp actually changes, so a real outcome of processing
			# must bump it or the UI silently never reflects it without a manual reload.
			doc.db_set(
				{"status": "Needs Review", "error": "No readable text found in this file."},
				commit=True,
			)
			return

		document_type = doc.document_type or "Expense Claim"
		if document_type == "Expense Claim":
			# Fast path: one minimal, purpose-built call, not generic-classify-then-remap
			# — see flow.services.expense_claim_extraction for why.
			result = _extract_for_expense_claim(text, doc.owner, model_name)
		else:
			result = _extract_generic(text, document_type, doc.owner, model_name)

		fields, line_items = result["fields"], result["line_items"]
		# has_content (not a plain "fields or line_items" truthiness check): the
		# Expense Claim fast path always merges in empty placeholders for unresolved
		# mandatory fields, so `fields` alone can no longer tell a genuine miss from
		# "found nothing, but company/currency resolved and are now sitting in there
		# as placeholders too" — see expense_claim_extraction.extract_expense_claim.
		has_data = result.get("has_content", bool(fields or line_items))
		usage = result.get("usage") or {}
		doc.db_set(
			{
				"raw_text": text,
				"ai_input": result.get("ai_input"),
				"extracted_fields": json.dumps(fields, default=str),
				"extracted_line_items": json.dumps(line_items, default=str),
				"field_mapping": json.dumps(result["mapping_meta"], default=str) if result["mapping_meta"] else None,
				"confidence": round((result.get("confidence") or 0) * 100, 1),
				# Added onto the existing totals, not overwritten: these three fields track
				# token spend across the entry's whole lifecycle (every Extract/Re-extract
				# here, plus any Create Document mapping calls added in flow.api.file2erp),
				# not just the most recent step. `doc` was loaded once at the top of this
				# call, before this run's own db_set, so doc.input_tokens etc. still hold
				# whatever was persisted by a prior run.
				"input_tokens": (doc.input_tokens or 0) + (usage.get("prompt_tokens") or 0),
				"output_tokens": (doc.output_tokens or 0) + (usage.get("completion_tokens") or 0),
				"total_tokens": (doc.total_tokens or 0) + (usage.get("total_tokens") or 0),
				"status": "Extracted" if has_data else "Needs Review",
				"error": result.get("notes") if not has_data else None,
			},
			commit=True,
		)
	except Exception as e:
		frappe.db.rollback()
		doc.db_set(
			{"status": "Failed", "error": str(e)[:5000]},
			commit=True,
		)
		frappe.log_error(
			title="Flow File2ERP processing failed",
			reference_doctype="Flow File2ERP",
			reference_name=name,
		)


def _extract_for_expense_claim(text: str, owner: str, model_name: str | None) -> dict:
	from flow.services import expense_claim_extraction

	result = expense_claim_extraction.extract_expense_claim(text, owner, model=model_name)
	return {
		"fields": result["fields"],
		"line_items": result["line_items"],
		"ai_input": result.get("ai_input"),
		"usage": result.get("usage") or {},
		"confidence": None,
		"notes": result.get("notes"),
		"mapping_meta": None,
		"has_content": result.get("has_content", False),
	}


def _extract_generic(text: str, document_type: str, owner: str, model_name: str | None) -> dict:
	"""Existing generic path, unchanged: a bare structuring call (it still does its own
	internal classification — simply unused now, since the target is the user's own
	explicit document_type choice, not a guess), then free-text renaming onto that
	DocType's real field names."""
	structured = structuring.extract_structured_data(text, model=model_name)
	fields, line_items = structured["fields"], structured["line_items"]
	mapping_meta = None

	if fields or line_items:
		mapped = field_mapping.map_entry_to_doctype(fields, line_items, document_type, model=model_name)
		fields, line_items = mapped["fields"], mapped["line_items"]
		fields = _autofill_employee(document_type, fields, owner)
		mapping_meta = {
			"doctype": document_type,
			"unmapped_fields": mapped["unmapped_fields"],
			"unmapped_line_item_fields": mapped["unmapped_line_item_fields"],
		}

	return {
		"fields": fields,
		"line_items": line_items,
		"ai_input": structured.get("ai_input"),
		"usage": structured.get("usage") or {},
		"confidence": structured.get("confidence"),
		"notes": structured.get("notes"),
		"mapping_meta": mapping_meta,
	}


def _supports_vision(model_name: str) -> bool:
	from flow.lib.model import supports_vision

	model_id = frappe.db.get_value("Flow Model", model_name, "model_id")
	return bool(model_id) and supports_vision(model_id)


def _autofill_employee(doctype: str, fields: dict, owner: str) -> dict:
	"""A receipt/expense document never names who's actually claiming it — the person
	who uploaded it is the obvious default. Only fills a field that's genuinely a Link
	to Employee and not already set from the document itself; same narrow-default spirit
	as flow.tools.builtins._with_create_defaults (posting_date, naming_series)."""
	employee_field = next(
		(df.fieldname for df in frappe.get_meta(doctype).fields if df.fieldtype == "Link" and df.options == "Employee"),
		None,
	)
	if not employee_field or fields.get(employee_field):
		return fields
	employee = frappe.db.get_value("Employee", {"user_id": owner}, "name")
	if not employee:
		return fields
	fields = dict(fields)
	fields[employee_field] = employee
	return fields
