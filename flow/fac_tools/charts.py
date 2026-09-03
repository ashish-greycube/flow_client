# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any, Literal

import frappe

from flow.lib.tool import tool

ChartType = Literal["bar", "line", "area", "donut", "funnel", "number"]


@tool
def create_chart(
	chart_type: ChartType,
	title: str,
	data: list[dict[str, Any]],
	category_field: str | None = None,
	value_fields: list[str] | None = None,
	series_labels: dict[str, str] | None = None,
	subtitle: str | None = None,
) -> dict[str, Any]:
	"""Render a chart inline in the chat from data you already have (e.g. from a report,
	database query, or record list) — the chart appears directly in your reply, nothing
	further is needed from you once this returns. Use this whenever the user asks to
	visualize, plot, chart, or graph data. Do not use create_dashboard_chart for this: that
	tool only creates a Frappe Dashboard Chart record and a link out to the Desk UI, it
	never shows anything inline here.

	- bar / line / area: `category_field` is the x-axis category (e.g. a date, name, or
	  status); `value_fields` lists one or more numeric fields to plot as series. Use
	  `series_labels` to give a field a nicer display name (e.g. {"grand_total": "Revenue"}).
	- donut / funnel: `category_field` is the slice/stage label; `value_fields` must have
	  exactly one numeric field.
	- number: a single KPI value. `value_fields` must have exactly one numeric field,
	  `data` should have exactly one row, `category_field` is ignored.
	"""
	if not data:
		raise frappe.ValidationError("`data` must have at least one row.")
	value_fields = value_fields or []
	labels = series_labels or {}

	if chart_type == "number":
		if len(value_fields) != 1:
			raise frappe.ValidationError("A `number` chart needs exactly one value field.")
		config = {"title": title, "value": _to_number(data[0].get(value_fields[0]))}
		return {"chart": {"kind": "number", "config": config}}

	if chart_type in ("donut", "funnel"):
		if len(value_fields) != 1:
			raise frappe.ValidationError(f"A `{chart_type}` chart needs exactly one value field.")
		if not category_field:
			raise frappe.ValidationError(f"A `{chart_type}` chart needs `category_field`.")
		value_field = value_fields[0]
		rows = [
			{"category": row.get(category_field), "value": _to_number(row.get(value_field))}
			for row in data
		]
		config = {
			"title": title,
			"subtitle": subtitle,
			"data": rows,
			"categoryColumn": "category",
			"valueColumn": "value",
		}
		return {"chart": {"kind": chart_type, "config": config}}

	# bar / line / area — frappe-ui's AxisChart looks up each series' values by
	# `row[series.name]`, so the series name IS the data key, not just a label;
	# build `data` keyed by the display name directly rather than passing a
	# separate label mapping through to the frontend.
	if not category_field:
		raise frappe.ValidationError("Axis charts (bar/line/area) need `category_field`.")
	if not value_fields:
		raise frappe.ValidationError("Axis charts (bar/line/area) need at least one value field.")
	series_names = [labels.get(field, field) for field in value_fields]
	rows = []
	for row in data:
		entry: dict[str, Any] = {"category": row.get(category_field)}
		for field, series_name in zip(value_fields, series_names):
			entry[series_name] = _to_number(row.get(field))
		rows.append(entry)
	config = {
		"title": title,
		"subtitle": subtitle,
		"data": rows,
		"xAxis": {"key": "category", "type": "category"},
		# frappe-ui's axis renderer always labels the y-axis "↑ {yAxis.title}" with no
		# guard for a missing title, so an empty string (not an absent key) is required
		# to avoid a literal "↑ undefined" printed on the chart.
		"yAxis": {"title": ""},
		"series": [{"name": name, "type": chart_type} for name in series_names],
	}
	return {"chart": {"kind": "axis", "config": config}}


def _to_number(value: Any) -> float:
	try:
		return float(value)
	except (TypeError, ValueError):
		return 0.0
