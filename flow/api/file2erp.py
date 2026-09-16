# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from flow.auth import require_flow_user


@frappe.whitelist()
def create_file2erp_entry(file: str) -> dict[str, Any]:
	"""Validate an uploaded File and create a File2ERP entry for it, defaulted to
	document_type="Expense Claim" (the doctype's own field default). Extraction does
	NOT start yet — it's scoped to document_type, so it waits for the user to confirm
	(or change) that choice via start_extraction."""
	require_flow_user()
	if not isinstance(file, str) or not file.strip():
		frappe.throw(_("File is required."), title=_("Invalid File"))

	from flow.services.validation import validate_file

	file_doc = frappe.get_doc("File", file.strip())
	if not frappe.has_permission("File", "read", doc=file_doc):
		frappe.throw(_("Not permitted to use this file."), frappe.PermissionError)
	validate_file(file_doc)

	if not frappe.has_permission("Flow File2ERP", "create"):
		frappe.throw(_("Not permitted to create File2ERP entries."), frappe.PermissionError)

	doc = frappe.get_doc(
		{
			"doctype": "Flow File2ERP",
			"file": file_doc.name,
			"file_name": file_doc.file_name,
			"file_size": file_doc.file_size,
		}
	).insert()
	return doc.as_dict()


@frappe.whitelist()
def start_extraction(name: str, document_type: str | None = None, force: bool | str = False) -> dict[str, Any]:
	"""Confirm (or change) this entry's target document_type and enqueue extraction —
	the explicit trigger that replaces the old auto-start-on-upload behavior. A no-op
	on status (still queues) if called again; flow.services.file2erp.process_entry
	itself is idempotent against re-running once raw_text/extracted_fields exist, unless
	`force=True` — the entry's "Re-extract Data" action, which always redoes the full
	pipeline (e.g. the first pass missed something, or the file needs a fresh read)."""
	require_flow_user()
	doc = frappe.get_doc("Flow File2ERP", name)
	if not frappe.has_permission("Flow File2ERP", "write", doc=doc):
		frappe.throw(_("Not permitted to edit this entry."), frappe.PermissionError)

	force = _is_truthy(force)
	if force and doc.status == "Document Created":
		frappe.throw(
			_("A document has already been created from this entry; it can no longer be re-extracted."),
			title=_("Not Allowed"),
		)

	if document_type:
		doc.document_type = document_type
		doc.save()

	frappe.enqueue(
		"flow.services.file2erp.process_entry",
		name=doc.name,
		force=force,
		queue="long",
		enqueue_after_commit=True,
	)
	return doc.as_dict()


@frappe.whitelist()
def delete_file2erp_entry(name: str) -> None:
	"""Delete a File2ERP entry. Ownership is asserted explicitly (Flow User has no
	doctype-level delete permission, mirroring flow.api.api.delete_chat's pattern for
	Flow Conversation/Flow Session) rather than granted broadly, so a user can only ever
	remove their own entries; System Manager (or another role with unrestricted delete)
	still gets through via has_permission. The underlying File is left alone — it may
	still be referenced elsewhere (a chat attachment, another record)."""
	require_flow_user()
	doc = frappe.get_doc("Flow File2ERP", name)
	if doc.owner != frappe.session.user and not frappe.has_permission("Flow File2ERP", "delete", doc=doc):
		frappe.throw(_("Not permitted to delete this entry."), frappe.PermissionError)
	frappe.delete_doc("Flow File2ERP", name, ignore_permissions=True)


@frappe.whitelist()
def get_file2erp_entry(name: str) -> dict[str, Any]:
	require_flow_user()
	doc = frappe.get_doc("Flow File2ERP", name)
	if not frappe.has_permission("Flow File2ERP", "read", doc=doc):
		frappe.throw(_("Not permitted to view this entry."), frappe.PermissionError)
	data = doc.as_dict()
	data["file_url"] = frappe.db.get_value("File", doc.file, "file_url") if doc.file else None
	return data


@frappe.whitelist()
def list_file2erp_entries(filters: dict | str | None = None, limit: int = 50) -> list[dict[str, Any]]:
	require_flow_user()
	limit = min(max(int(limit or 50), 1), 200)
	resolved_filters = _parse_dict(filters) or {}
	# Scoped to the caller's own entries regardless of role, not just left to the
	# doctype's if_owner permission — mirrors flow.routing.conversation.chat_history()'s
	# explicit owner filter for "Recent Chats". if_owner alone would leak every entry to
	# a user who also holds an unrestricted role (e.g. System Manager), since Frappe
	# takes the most-permissive combination across a user's roles. A caller-supplied
	# "owner" is overwritten, not merged, so it can't be used to widen the query.
	resolved_filters["owner"] = frappe.session.user
	return frappe.get_list(
		"Flow File2ERP",
		filters=resolved_filters,
		fields=[
			"name",
			"file",
			"file_name",
			"file_size",
			"file_type",
			"status",
			"document_type",
			"confidence",
			"created_document_type",
			"created_document",
			"creation",
			"modified",
		],
		order_by="creation desc",
		limit_page_length=limit,
	)


@frappe.whitelist()
def update_file2erp_data(
	name: str, fields: dict | str | None = None, line_items: list | str | None = None
) -> dict[str, Any]:
	"""Save the user's corrections to a File2ERP entry's structured data."""
	require_flow_user()
	doc = frappe.get_doc("Flow File2ERP", name)
	if not frappe.has_permission("Flow File2ERP", "write", doc=doc):
		frappe.throw(_("Not permitted to edit this entry."), frappe.PermissionError)

	parsed_fields = _parse_dict(fields)
	parsed_items = _parse_list(line_items)
	if parsed_fields is not None:
		doc.extracted_fields = json.dumps(parsed_fields, default=str)
	if parsed_items is not None:
		doc.extracted_line_items = json.dumps(parsed_items, default=str)
	if doc.status == "Needs Review" and (parsed_fields or parsed_items):
		doc.status = "Extracted"
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def open_chat_session(name: str) -> dict[str, Any]:
	"""Stage this entry's already-extracted text as a chat attachment — no re-parsing —
	so the frontend can hand it straight to the normal send()/start_run flow."""
	require_flow_user()
	doc = frappe.get_doc("Flow File2ERP", name)
	if not frappe.has_permission("Flow File2ERP", "read", doc=doc):
		frappe.throw(_("Not permitted to view this entry."), frappe.PermissionError)
	if not doc.raw_text:
		frappe.throw(
			_("This file hasn't finished processing yet."), title=_("Not Ready")
		)

	from flow.flow.doctype.flow_session_attachment.flow_session_attachment import stage_extracted

	return stage_extracted(doc.file, doc.raw_text)


@frappe.whitelist()
def create_document_from_entry(
	name: str,
	doctype: str,
	fields: dict | str | None = None,
	line_items: list | str | None = None,
) -> dict[str, Any]:
	"""Button-triggered shortcut: map this entry's (possibly caller-supplied, otherwise
	stored) data onto `doctype` and create it directly — separate from the natural-
	language chat path. Not a tool call, so it has no agent-run confirmation pause; the
	caller (the frontend) must confirm with the user before calling this."""
	require_flow_user()
	doc = frappe.get_doc("Flow File2ERP", name)
	if not frappe.has_permission("Flow File2ERP", "write", doc=doc):
		frappe.throw(_("Not permitted to edit this entry."), frappe.PermissionError)
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("Not permitted to create {0}.").format(doctype), frappe.PermissionError)

	from flow.services import document_creation, document_mapping

	source_fields = _parse_dict(fields)
	if source_fields is None:
		source_fields = json.loads(doc.extracted_fields) if doc.extracted_fields else {}
	source_items = _parse_list(line_items)
	if source_items is None:
		source_items = json.loads(doc.extracted_line_items) if doc.extracted_line_items else []

	if doctype == doc.document_type:
		# Fast path: extraction (flow.services.file2erp.process_entry) already produced
		# data shaped for this exact DocType, so there's nothing left to remap — skip
		# document_mapping's LLM calls entirely and create directly. This is the common
		# case (e.g. Expense Claim -> Extract -> Review -> Create with no DocType
		# change) and the one the whole pipeline is optimized to make fast.
		mapped_fields, mapped_items, notes = source_fields, source_items, None
	else:
		# Schema-aware, context-aware mapping — only needed when re-targeting to a
		# DocType different from the one extraction was scoped to. Fetches the target
		# DocType's real field schema (types, mandatory, Link/Select options, child
		# table), resolves Link fields against actual existing records via a bounded DB
		# search + AI pick, and uses the uploader's Employee/Company context for fields
		# the document itself can never state. See flow.services.document_mapping.
		mapped = document_mapping.map_to_document(source_fields, source_items, doctype, doc.owner)
		mapped_fields, mapped_items = mapped["fields"], mapped["line_items"]
		notes = mapped["notes"]
		_accumulate_token_usage(doc, mapped.get("usage"))

	# Validated against the target DocType's real mandatory fields (parent and child
	# table) before ever attempting creation — a clear, actionable message instead of
	# Frappe's own raw "Value missing" exception from deep inside document insertion.
	validation_errors = document_creation.find_missing_mandatory(doctype, mapped_fields, mapped_items)
	if validation_errors:
		return {
			"result": {
				"doctype": doctype,
				"created": [],
				"failures": [{"error": _("Missing required field(s): {0}").format(", ".join(validation_errors))}],
			},
			"missing_mandatory": validation_errors,
			"notes": notes,
		}

	result = document_creation.create_from_mapped(doctype, mapped_fields, mapped_items or None)
	if result.get("created"):
		created_name = result["created"][0]
		doc.created_document_type = doctype
		doc.created_document = created_name
		doc.status = "Document Created"
		doc.save()
		_attach_source_file(doc, doctype, created_name)
		_link_back_to_entry(doc, doctype, created_name)

	return {
		"result": result,
		# Empty by construction here: the validation_errors gate above already returned
		# early if anything mandatory was still missing, so creation only ever reaches
		# this point with a complete document.
		"missing_mandatory": [],
		"notes": notes,
	}


def _accumulate_token_usage(doc, usage: dict[str, Any] | None) -> None:
	"""Adds one LLM call's usage onto this entry's running total across its whole
	lifecycle (Extract/Re-extract in flow.services.file2erp, plus any Create Document
	mapping calls here) rather than overwriting it."""
	if not usage:
		return
	doc.db_set(
		{
			"input_tokens": (doc.input_tokens or 0) + (usage.get("prompt_tokens") or 0),
			"output_tokens": (doc.output_tokens or 0) + (usage.get("completion_tokens") or 0),
			"total_tokens": (doc.total_tokens or 0) + (usage.get("total_tokens") or 0),
		},
		commit=True,
	)


def _attach_source_file(doc, doctype: str, docname: str) -> None:
	"""Best-effort: a failure here shouldn't undo an otherwise-successful document
	creation, just leave the document without its supporting file attached."""
	from flow.services import document_creation

	try:
		document_creation.attach_source_file(doc.file, doctype, docname)
	except Exception:
		frappe.log_error(
			title="Flow File2ERP: could not attach source file",
			reference_doctype="Flow File2ERP",
			reference_name=doc.name,
		)


def _link_back_to_entry(doc, doctype: str, docname: str) -> None:
	"""Leaves a comment on the newly created document linking back to the File2ERP
	entry it came from, so anyone looking at the ERPNext record later can trace it back
	to the original upload/extraction/review. Best-effort, same reasoning as
	_attach_source_file — never lets this fail the actual creation."""
	try:
		from frappe.utils import escape_html, get_url

		link = get_url(f"/app/flow-chat/file2erp/{doc.name}")
		label = escape_html(doc.file_name or doc.name)
		frappe.get_doc(doctype, docname).add_comment(
			"Comment",
			_('Created from File2ERP entry: <a href="{0}">{1}</a>').format(link, label),
		)
	except Exception:
		frappe.log_error(
			title="Flow File2ERP: could not link back to entry",
			reference_doctype="Flow File2ERP",
			reference_name=doc.name,
		)


def _is_truthy(value: Any) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, int | float):
		return bool(value)
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def _parse_dict(value: Any) -> dict[str, Any] | None:
	if value in (None, ""):
		return None
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except (TypeError, ValueError):
			frappe.throw(_("Expected a JSON object."), title=_("Invalid Input"))
	if not isinstance(value, dict):
		frappe.throw(_("Expected a JSON object."), title=_("Invalid Input"))
	return value


def _parse_list(value: Any) -> list[Any] | None:
	if value in (None, ""):
		return None
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except (TypeError, ValueError):
			frappe.throw(_("Expected a JSON array."), title=_("Invalid Input"))
	if not isinstance(value, list):
		frappe.throw(_("Expected a JSON array."), title=_("Invalid Input"))
	return value
