# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any

import frappe

from flow.lib.tool import tool

COMMON_DOCTYPES = ("User", "DocType", "Contact", "Customer", "Supplier", "Item", "Company", "Employee", "Task", "Project")
MAX_SEARCH_LIMIT = 200


@tool
def search_documents(query: str, limit: int = 20) -> dict[str, Any]:
	"""Search common Frappe DocTypes globally while respecting record permissions."""
	limit = _limit(limit)
	results = []
	searched = []
	for doctype in COMMON_DOCTYPES:
		if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
			continue
		searched.append(doctype)
		try:
			rows = frappe.get_list(
				doctype,
				filters={"name": ["like", f"%{query}%"]},
				fields=["name"],
				limit=min(5, limit),
			)
		except (frappe.PermissionError, frappe.ValidationError):
			continue
		results.extend({"doctype": doctype, **dict(row)} for row in rows)
	return {"success": True, "query": query, "results": results[:limit], "count": min(len(results), limit), "total_found": len(results), "searched_doctypes": searched}


@tool
def search_doctype(doctype: str, query: str, limit: int = 20) -> dict[str, Any]:
	"""Search text fields in one DocType with row-level permission filtering."""
	_assert_readable(doctype)
	meta = frappe.get_meta(doctype)
	fields = []
	if meta.title_field:
		fields.append(meta.title_field)
	fields.extend(
		field.fieldname
		for field in meta.fields
		if field.fieldtype in {"Data", "Text", "Small Text"} and not field.hidden
	)
	fields = list(dict.fromkeys(fields))[:5] or ["name"]
	rows = frappe.get_list(
		doctype,
		or_filters=[[doctype, field, "like", f"%{query}%"] for field in fields],
		fields=list(dict.fromkeys(["name", *fields])),
		limit=_limit(limit),
		order_by="modified desc",
	)
	return {"success": True, "doctype": doctype, "query": query, "results": rows, "count": len(rows), "search_fields": fields}


@tool
def search_link(doctype: str, query: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
	"""Search valid Link values using Frappe's permission-aware link search."""
	_assert_readable(doctype)
	from frappe.desk.search import search_link as frappe_search_link

	applied = filters or {}
	rows = frappe_search_link(doctype=doctype, txt=query, filters=applied)
	return {"success": True, "doctype": doctype, "query": query, "results": rows, "count": len(rows), "filters_applied": applied}


def _assert_readable(doctype: str) -> None:
	if not frappe.db.exists("DocType", doctype):
		raise frappe.DoesNotExistError(f"DocType {doctype!r} does not exist")
	frappe.has_permission(doctype, "read", throw=True)


def _limit(value: int) -> int:
	return min(max(int(value), 1), MAX_SEARCH_LIMIT)
