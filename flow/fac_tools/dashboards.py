# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import json
from typing import Any, Literal

import frappe

from flow.lib.tool import tool

VISUAL_TYPES = {"line": "Line", "bar": "Bar", "percentage": "Percentage", "pie": "Pie", "donut": "Donut", "heatmap": "Heatmap"}
NUMERIC_FIELDTYPES = {"Int", "Float", "Currency", "Percent", "Duration"}
DATE_FIELDTYPES = {"Date", "Datetime"}


@tool(requires_confirmation=True)
def create_dashboard(
	dashboard_name: str,
	chart_names: list[str],
	doctype: str | None = None,
	filters: dict[str, Any] | None = None,
	share_with: list[str] | None = None,
	auto_refresh: bool = True,
	refresh_interval: Literal["5_minutes", "15_minutes", "30_minutes", "1_hour", "24_hours"] = "1_hour",
	template_type: Literal["sales", "financial", "inventory", "hr", "executive", "custom"] = "custom",
	mobile_optimized: bool = True,
) -> dict[str, Any]:
	"""Create a standard Frappe Dashboard from existing Dashboard Charts."""
	frappe.has_permission("Dashboard", "create", throw=True)
	if not chart_names:
		raise frappe.ValidationError("At least one Dashboard Chart is required")
	missing = [name for name in chart_names if not frappe.db.exists("Dashboard Chart", name)]
	if missing:
		raise frappe.DoesNotExistError(f"Dashboard Charts not found: {', '.join(missing)}")
	dashboard = frappe.get_doc(
		{
			"doctype": "Dashboard",
			"dashboard_name": dashboard_name,
			"is_standard": 0,
			"charts": [{"chart": name, "width": "Half"} for name in chart_names],
			"chart_options": json.dumps({"filters": filters or {}, "refresh_interval": refresh_interval}),
		}
	).insert()
	shared = _share("Dashboard", dashboard.name, share_with or [])
	return {
		"success": True,
		"dashboard_type": "frappe_dashboard",
		"dashboard_name": dashboard.dashboard_name,
		"dashboard_id": dashboard.name,
		"dashboard_url": f"/app/dashboard/{dashboard.name}",
		"charts": chart_names,
		"charts_linked": len(chart_names),
		"shared_with": shared,
		"auto_refresh": auto_refresh,
		"mobile_optimized": mobile_optimized,
		"template_type": template_type,
		"primary_doctype": doctype,
	}


@tool(requires_confirmation=True)
def create_dashboard_chart(
	chart_name: str,
	chart_type: Literal["line", "bar", "percentage", "pie", "donut", "heatmap"],
	doctype: str,
	aggregate_function: Literal["Count", "Sum", "Average", "Group By"] = "Count",
	value_based_on: str | None = None,
	based_on: str | None = None,
	time_series_based_on: str | None = None,
	timespan: Literal["Last Year", "Last Quarter", "Last Month", "Last Week"] = "Last Month",
	time_interval: Literal["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"] = "Daily",
	filters: dict[str, Any] | None = None,
	color: str | None = None,
	dashboard_name: str | None = None,
) -> dict[str, Any]:
	"""Create a permission-checked Frappe Dashboard Chart and optionally add it to a dashboard."""
	frappe.has_permission(doctype, "read", throw=True)
	frappe.has_permission("Dashboard Chart", "create", throw=True)
	meta = frappe.get_meta(doctype)
	field_map = {field.fieldname: field for field in meta.fields}
	if aggregate_function in {"Sum", "Average"}:
		_validate_field(field_map, value_based_on, NUMERIC_FIELDTYPES, "numeric value_based_on")
	time_field = time_series_based_on or (based_on if based_on in field_map and field_map[based_on].fieldtype in DATE_FIELDTYPES else None)
	if chart_type in {"line", "heatmap"}:
		_validate_field(field_map, time_field, DATE_FIELDTYPES, "date time_series_based_on")
	group_field = based_on
	if aggregate_function == "Group By" and not group_field:
		raise frappe.ValidationError("based_on is required for Group By charts")
	doc = frappe.get_doc(
		{
			"doctype": "Dashboard Chart",
			"chart_name": chart_name,
			"chart_type": aggregate_function,
			"document_type": doctype,
			"based_on": time_field or "creation",
			"value_based_on": value_based_on,
			"group_by_based_on": group_field,
			"group_by_type": "Count" if aggregate_function == "Group By" else None,
			"timeseries": int(bool(time_field)),
			"timespan": timespan,
			"time_interval": time_interval,
			"filters_json": json.dumps(filters or {}),
			"type": VISUAL_TYPES[chart_type],
			"color": color,
			"is_standard": 0,
		}
	).insert()
	added = _add_to_dashboard(doc.name, dashboard_name) if dashboard_name else False
	return {
		"success": True,
		"chart_name": doc.chart_name,
		"chart_id": doc.name,
		"chart_type": chart_type,
		"aggregate_function": aggregate_function,
		"chart_url": f"/app/dashboard-chart/{doc.name}",
		"added_to_dashboard": dashboard_name if added else None,
	}


@tool
def list_user_dashboards(search: str | None = None, limit: int = 50) -> dict[str, Any]:
	"""List standard Frappe Dashboards readable by the current user."""
	filters = {"dashboard_name": ["like", f"%{search}%"]} if search else None
	rows = frappe.get_list(
		"Dashboard",
		filters=filters,
		fields=["name", "dashboard_name", "is_default", "module", "modified", "owner"],
		order_by="modified desc",
		limit=min(max(int(limit), 1), 200),
	)
	return {"success": True, "dashboards": rows, "count": len(rows)}


def _validate_field(field_map: dict, fieldname: str | None, allowed_types: set[str], label: str) -> None:
	if not fieldname or fieldname not in field_map or field_map[fieldname].fieldtype not in allowed_types:
		raise frappe.ValidationError(f"A valid {label} field is required")


def _add_to_dashboard(chart: str, dashboard: str) -> bool:
	doc = frappe.get_doc("Dashboard", dashboard)
	doc.check_permission("write")
	if chart not in {row.chart for row in doc.charts}:
		doc.append("charts", {"chart": chart, "width": "Half"})
		doc.save()
	return True


def _share(doctype: str, name: str, users_or_roles: list[str]) -> list[str]:
	shared = set()
	for value in users_or_roles:
		users = [value] if frappe.db.exists("User", value) else frappe.get_all("Has Role", {"role": value}, pluck="parent")
		for user in users:
			frappe.share.add(doctype, name, user, read=1)
			shared.add(user)
	return sorted(shared)
