from __future__ import annotations

import frappe


def macro_query_conditions(user: str | None = None) -> str:
	return _owner_query("Flow Macro", user)


def macro_run_query_conditions(user: str | None = None) -> str:
	return _owner_query("Flow Macro Run", user)


def has_macro_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	user = user or frappe.session.user
	if _is_system_manager(user) or ptype == "create":
		return None
	return doc.owner == user


def has_macro_run_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	user = user or frappe.session.user
	if _is_system_manager(user):
		return None
	if ptype == "create":
		return False
	return doc.owner == user


def _owner_query(doctype: str, user: str | None) -> str:
	user = user or frappe.session.user
	if _is_system_manager(user):
		return ""
	return f"`tab{doctype}`.`owner` = {frappe.db.escape(user)}"


def _is_system_manager(user: str) -> bool:
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)
