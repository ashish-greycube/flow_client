# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Turn mapped fields (+ optional line items) into an actual Frappe document. Reuses the
existing generic `create` tool's permission check and smart defaults (posting date,
naming series) verbatim, so a record created this way is indistinguishable from one the
OCR Agent created conversationally."""

from __future__ import annotations

from typing import Any

_LAYOUT_FIELDTYPES = frozenset({"Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Button"})
# naming_series is mandatory on many doctypes but never worth blocking creation over:
# Frappe autonames from it and flow.tools.builtins._with_recent_company_naming_series
# already picks a sensible default at create time when it's left unset.
_EXCLUDED_MANDATORY_FIELDS = frozenset({"naming_series"})


def create_from_mapped(
	doctype: str,
	fields: dict[str, Any],
	line_items: list[dict[str, Any]] | None = None,
	child_table_fieldname: str | None = None,
) -> dict[str, Any]:
	"""Create one `doctype` record from `fields`, nesting `line_items` under its child
	table if given. Returns the same {"doctype", "created", "failures"} shape as the
	underlying `create` tool."""
	import frappe
	from frappe import _

	from flow.tools.builtins import create

	info = get_child_table_info(doctype)
	values = _normalize_date_fields(dict(fields or {}), frappe.get_meta(doctype))
	if line_items:
		fieldname = child_table_fieldname or (info[0] if info else None)
		if not fieldname:
			frappe.throw(
				_("{0} has no child table to hold line items.").format(doctype),
				title=_("Cannot Create Document"),
			)
		if info:
			child_meta = frappe.get_meta(info[1])
			line_items = [_normalize_date_fields(row, child_meta) for row in line_items]
		values[fieldname] = line_items

	return create(doctype=doctype, records=[values])


def _normalize_date_fields(values: dict[str, Any], meta) -> dict[str, Any]:
	"""AI-extracted dates arrive in whatever format the source document/OCR used
	(e.g. "20/03/2025", "20-Mar-2025") — Frappe's Date/Datetime columns need
	yyyy-mm-dd, and MySQL rejects anything else outright with a raw "Incorrect date
	value" error rather than reinterpreting it. Runs for every doctype's fields here
	(parent and child), not just Expense Claim's expense_date, since any target
	DocType can have its own date fields extracted the same loosely-formatted way."""
	import frappe
	from frappe.utils import get_datetime, getdate

	date_fields = {df.fieldname: df.fieldtype for df in meta.fields if df.fieldtype in ("Date", "Datetime")}
	if not date_fields:
		return values

	out = dict(values)
	day_first = _prefers_day_first()
	for fieldname, fieldtype in date_fields.items():
		value = out.get(fieldname)
		if not isinstance(value, str) or not value.strip():
			continue
		try:
			if fieldtype == "Date":
				out[fieldname] = getdate(value, parse_day_first=day_first).isoformat()
			else:
				out[fieldname] = get_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
		except Exception:
			# Left as-is: a genuinely unparsable string will still fail at insert, but
			# with Frappe's own clearer validation error rather than silently vanishing.
			frappe.log_error(title="Flow File2ERP: could not normalize date field", message=f"{fieldname}={value!r}")
	return out


def _prefers_day_first() -> bool:
	"""Ambiguous two-digit-day dates (e.g. "03/04/2025") can't be resolved from the
	string alone — fall back to whichever convention this site's own date_format
	uses, rather than assuming either US or international style."""
	import frappe

	date_format = frappe.get_system_settings("date_format") or "yyyy-mm-dd"
	return date_format.strip().lower().startswith("d")


def find_missing_mandatory(
	doctype: str,
	fields: dict[str, Any],
	line_items: list[dict[str, Any]] | None = None,
) -> list[str]:
	"""Human-readable labels of mandatory `doctype` (and its child table's) fields that
	are still empty in `fields`/`line_items` — checked explicitly before creation so the
	user sees one clear "missing X, Y" message instead of Frappe's own raw "Value
	missing" exception surfacing from deep inside document insertion."""
	import frappe
	from frappe import _

	meta = frappe.get_meta(doctype)
	missing: list[str] = []
	for df in meta.fields:
		if not df.reqd or df.read_only or df.hidden or df.default:
			continue
		if df.fieldtype in _LAYOUT_FIELDTYPES or df.fieldname in _EXCLUDED_MANDATORY_FIELDS:
			continue
		if df.fieldtype == "Table":
			if not line_items:
				missing.append(df.label or df.fieldname)
			continue
		if (fields or {}).get(df.fieldname) in (None, ""):
			missing.append(df.label or df.fieldname)

	child_info = get_child_table_info(doctype)
	if child_info and line_items:
		child_mandatory = [
			cdf
			for cdf in frappe.get_meta(child_info[1]).fields
			if cdf.reqd
			and not cdf.read_only
			and not cdf.hidden
			and not cdf.default
			and cdf.fieldtype not in _LAYOUT_FIELDTYPES
			and cdf.fieldtype != "Table"
		]
		for idx, row in enumerate(line_items, start=1):
			for cdf in child_mandatory:
				if (row or {}).get(cdf.fieldname) in (None, ""):
					missing.append(_("{0} (line {1})").format(cdf.label or cdf.fieldname, idx))

	return missing


def attach_source_file(source_file: str, doctype: str, docname: str) -> None:
	"""Attach the originally uploaded File to a newly created document, so the ERPNext
	record carries its supporting receipt/invoice straight from creation. Inserts a NEW
	File record pointing at the same stored content rather than repointing the existing
	one — the source File must stay exactly as File2ERP left it (unattached, owner-only)
	for File2ERP's own preview/permission model; File.save_file's own content-hash dedup
	means this reuses the existing bytes on disk instead of duplicating them."""
	import frappe

	source = frappe.get_doc("File", source_file)
	frappe.get_doc(
		{
			"doctype": "File",
			"file_url": source.file_url,
			"file_name": source.file_name,
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
			"is_private": source.is_private,
		}
	).insert(ignore_permissions=True)


def get_child_table_info(doctype: str) -> tuple[str, str] | None:
	"""(fieldname, child_doctype) for the table line items should be nested under and
	mapped against — e.g. ("items", "Sales Invoice Item") — or None if `doctype` has no
	child table. Line items must be field-mapped against the *child* doctype's fields,
	not the parent's."""
	import frappe

	meta = frappe.get_meta(doctype)
	table_fields = [df for df in meta.fields if df.fieldtype == "Table"]
	if not table_fields:
		return None
	# Most doctypes with line items name the field "items" (Sales Invoice, Purchase
	# Order, ...); prefer it when a doctype has more than one child table.
	for df in table_fields:
		if df.fieldname == "items":
			return df.fieldname, df.options
	return table_fields[0].fieldname, table_fields[0].options
