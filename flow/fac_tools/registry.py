# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import frappe

from flow.fac_tools.analysis import analyze_business_data, run_database_query, run_python_code
from flow.fac_tools.charts import create_chart
from flow.fac_tools.dashboards import create_dashboard, create_dashboard_chart, list_user_dashboards
from flow.fac_tools.exports import export_excel
from flow.fac_tools.files import extract_file_content
from flow.fac_tools.reports import generate_report, report_list, report_requirements
from flow.fac_tools.search import search_doctype, search_documents, search_link
from flow.fac_tools.workflow import get_pending_approvals
from flow.lib.tool import Tool

FAC_TOOLS: list[Tool] = [
	search_documents,
	search_doctype,
	search_link,
	report_list,
	report_requirements,
	generate_report,
	export_excel,
	get_pending_approvals,
	run_python_code,
	analyze_business_data,
	run_database_query,
	extract_file_content,
	create_dashboard,
	create_dashboard_chart,
	list_user_dashboards,
	create_chart,
]


def sync_fac_tools() -> None:
	"""Upsert advanced tools without changing Flow's upstream builtin registry."""
	for advanced_tool in FAC_TOOLS:
		_sync_tool(advanced_tool)
	_attach_to_builtin_agent()
	from flow.fac_tools.prebuilt_agents import sync_prebuilt_agents

	sync_prebuilt_agents()


def _sync_tool(advanced_tool: Tool) -> None:
	import_path = f"{advanced_tool.func.__module__}.{advanced_tool.name}"
	values = {
		"title": advanced_tool.name.replace("_", " ").title(),
		"type": "Imported",
		"import_path": import_path,
		"description": advanced_tool.description,
		"enabled": 1,
		"requires_confirmation": int(advanced_tool.requires_confirmation),
		"is_system_generated": 1,
	}
	if frappe.db.exists("Flow Tool", advanced_tool.name):
		if not frappe.db.get_value("Flow Tool", advanced_tool.name, "is_system_generated"):
			return
		frappe.db.set_value("Flow Tool", advanced_tool.name, values, update_modified=False)
		return
	frappe.get_doc({"doctype": "Flow Tool", "slug": advanced_tool.name, **values}).insert(
		ignore_permissions=True
	)


def _attach_to_builtin_agent() -> None:
	if not frappe.db.exists("Flow Agent", "Flow"):
		return
	agent = frappe.get_doc("Flow Agent", "Flow")
	if not agent.is_system_generated:
		return
	existing = {row.tool for row in agent.tools}
	changed = False
	for advanced_tool in FAC_TOOLS:
		if advanced_tool.name not in existing:
			agent.append("tools", {"tool": advanced_tool.name})
			changed = True
	if changed:
		agent.save(ignore_permissions=True)
