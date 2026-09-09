# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import frappe

from flow.agent_instructions import SALES_INVOICE_CREATION_INSTRUCTIONS

SALES_INVOICE_COMMAND = "create-sales-invoice"
# Kept for the deferred Skills rollout. The AR agent now owns these instructions directly.
SALES_INVOICE_INSTRUCTIONS = SALES_INVOICE_CREATION_INSTRUCTIONS


def sync_prebuilt_skills() -> None:
	"""Create or refresh Flow's example ERPNext skill."""
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return

	values = {
		"title": "Create Sales Invoice",
		"description": "Validate invoice details and create an ERPNext Sales Invoice draft after approval.",
		"instructions": SALES_INVOICE_INSTRUCTIONS,
		"tools": [{"tool": tool} for tool in ("describe", "read", "create")],
		"enabled": 1,
		"is_system_generated": 1,
	}
	if not frappe.db.exists("Flow Skill", SALES_INVOICE_COMMAND):
		frappe.get_doc(
			{"doctype": "Flow Skill", "command": SALES_INVOICE_COMMAND, **values}
		).insert(ignore_permissions=True)
		return

	doc = frappe.get_doc("Flow Skill", SALES_INVOICE_COMMAND)
	if not doc.is_system_generated:
		return
	for fieldname, value in values.items():
		if fieldname != "tools":
			doc.set(fieldname, value)
	doc.set("tools", values["tools"])
	doc.save(ignore_permissions=True)
