# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any

import frappe
from frappe.query_builder import DocType

from flow.lib.tool import tool

MAX_TRANSITION_DOCS = 20


@tool
def get_pending_approvals(
	doctype: str | None = None, limit: int = 50, include_actions: bool = True
) -> dict[str, Any]:
	"""List open Workflow Actions available to the current user, grouped by DocType."""
	limit = min(max(int(limit), 1), 200)
	user = frappe.session.user
	workflow_action = DocType("Workflow Action")
	permitted_role = DocType("Workflow Action Permitted Role")
	role_matches = (
		frappe.qb.from_(workflow_action)
		.join(permitted_role)
		.on(workflow_action.name == permitted_role.parent)
		.select(workflow_action.name)
		.where(permitted_role.role.isin(frappe.get_roles(user)))
	)
	query = (
		frappe.qb.from_(workflow_action)
		.select(
			workflow_action.name,
			workflow_action.reference_doctype,
			workflow_action.reference_name,
			workflow_action.workflow_state,
			workflow_action.user,
			workflow_action.creation,
		)
		.where(workflow_action.status == "Open")
		.orderby(workflow_action.creation, order=frappe.qb.desc)
		.limit(limit)
	)
	if user != "Administrator":
		query = query.where(workflow_action.name.isin(role_matches) | (workflow_action.user == user))
	if doctype:
		query = query.where(workflow_action.reference_doctype == doctype)
	rows = query.run(as_dict=True)
	grouped: dict[str, list[dict[str, Any]]] = {}
	seen: set[tuple[str, str]] = set()
	for row in rows:
		if not frappe.has_permission(row.reference_doctype, "read", row.reference_name):
			continue
		key = (row.reference_doctype, row.reference_name)
		entry = {
			"workflow_action": row.name,
			"document_name": row.reference_name,
			"workflow_state": row.workflow_state,
			"creation": row.creation,
		}
		if include_actions and key not in seen and len(seen) < MAX_TRANSITION_DOCS:
			seen.add(key)
			entry["available_actions"] = _transitions(*key)
		grouped.setdefault(row.reference_doctype, []).append(entry)
	return {
		"success": True,
		"total_pending": sum(len(items) for items in grouped.values()),
		"doctypes_with_pending": list(grouped),
		"pending_approvals": grouped,
	}


def _transitions(doctype: str, name: str) -> list[dict[str, Any]]:
	try:
		from frappe.model.workflow import get_transitions

		return [
			{"action": transition.get("action"), "next_state": transition.get("next_state")}
			for transition in get_transitions(frappe.get_doc(doctype, name))
		]
	except Exception:
		return []
