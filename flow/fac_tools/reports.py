# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any, Literal

import frappe

from flow.fac_tools.report_filters import apply_defaults, discover_filters
from flow.lib.tool import tool

MAX_REPORT_ROWS = 500


@tool
def report_list(
	module: str | None = None,
	report_type: Literal["Report Builder", "Query Report", "Script Report", "Custom Report"] | None = None,
) -> dict[str, Any]:
	"""Discover enabled Frappe reports the current user is permitted to run."""
	filters: dict[str, Any] = {"disabled": 0}
	if module:
		filters["module"] = module
	if report_type:
		filters["report_type"] = report_type
	rows = frappe.get_all(
		"Report",
		filters=filters,
		fields=["name", "report_name", "report_type", "module", "ref_doctype", "is_standard"],
		order_by="report_name",
		limit=500,
	)
	reports = [dict(row) for row in rows if _can_run(row.name)]
	return {"success": True, "reports": reports, "count": len(reports), "filters_applied": filters}


@tool
def report_requirements(
	report_name: str,
	include_metadata: bool = False,
	include_columns: bool = True,
	include_filters: bool = True,
) -> dict[str, Any]:
	"""Inspect a report's columns, declared filters, defaults, and execution requirements."""
	report = _report(report_name)
	filters = [_filter_dict(row) for row in (report.filters or [])]
	diagnostics = []
	if not filters:
		filters, diagnostics = discover_filters(report.name)
	columns = [row.as_dict(no_default_fields=True) for row in (report.columns or [])]
	result: dict[str, Any] = {
		"success": True,
		"report_name": report.name,
		"report_type": report.report_type,
		"reference_doctype": report.ref_doctype,
		"prepared_report": bool(report.prepared_report),
		"filter_discovery_status": "declared" if filters else "unresolved" if diagnostics else "no_filters_declared",
	}
	if diagnostics:
		result["discovery_diagnostics"] = diagnostics
	if include_filters:
		result["filters"] = filters
		result["required_filters"] = [row["fieldname"] for row in filters if row.get("required")]
	if include_columns:
		result["columns"] = columns
	if include_metadata:
		result["metadata"] = {
			"module": report.module,
			"is_standard": report.is_standard,
			"owner": report.owner,
			"modified": report.modified,
		}
	return result


@tool
def generate_report(
	report_name: str,
	filters: dict[str, Any] | None = None,
	format: Literal["json", "csv", "excel"] = "json",
) -> dict[str, Any]:
	"""Execute a permitted Script, Query, or Custom Report and return at most 500 rows."""
	report = _report(report_name)
	if report.report_type == "Report Builder":
		raise frappe.ValidationError("Report Builder reports are not supported by this tool")
	from frappe.desk.query_report import run

	definitions = [_filter_dict(row) for row in (report.filters or [])]
	if not definitions:
		definitions, _ = discover_filters(report.name)
	applied = apply_defaults(filters or {}, definitions)
	response = run(
		report_name=report.name,
		filters=applied,
		user=frappe.session.user,
		ignore_prepared_report=True,
		js_filters=definitions,
	)
	data = [dict(row) if isinstance(row, dict) else row for row in (response.get("result") or [])]
	columns = response.get("columns") or []
	if format == "json":
		return {
			"success": True,
			"report_name": report.name,
			"report_type": report.report_type,
			"data": data[:MAX_REPORT_ROWS],
			"data_count": len(data),
			"truncated": len(data) > MAX_REPORT_ROWS,
			"columns": columns,
			"message": response.get("message"),
			"chart": response.get("chart"),
			"report_summary": response.get("report_summary"),
			"filters_applied": applied,
		}
	frappe.permissions.can_export(report.ref_doctype, raise_exception=True)
	return _export(report.name, columns, data, format)


def _report(name: str):
	if not frappe.db.exists("Report", name):
		raise frappe.DoesNotExistError(f"Report {name!r} does not exist")
	from frappe.desk.query_report import get_report_doc

	return get_report_doc(name)


def _can_run(name: str) -> bool:
	try:
		_report(name)
		return True
	except (frappe.PermissionError, frappe.DoesNotExistError):
		return False


def _filter_dict(row) -> dict[str, Any]:
	data = row.as_dict(no_default_fields=True) if hasattr(row, "as_dict") else dict(row)
	options = data.get("options")
	if data.get("fieldtype") in {"Select", "Autocomplete"} and isinstance(options, str):
		data["options"] = [value.strip() for value in options.replace("\\n", "\n").splitlines() if value.strip()]
	data["required"] = bool(data.pop("reqd", data.get("mandatory", False)))
	return data


def _export(report_name: str, columns: list, rows: list, output_format: str) -> dict[str, Any]:
	from frappe.utils.file_manager import save_file

	fieldnames = [column.get("fieldname") or column.get("label") for column in columns]
	fieldnames = [field for field in fieldnames if field]
	values = [[row.get(field) for field in fieldnames] if isinstance(row, dict) else row for row in rows]
	if output_format == "excel":
		from frappe.utils.xlsxutils import make_xlsx

		payload = make_xlsx([fieldnames, *values], report_name).getvalue()
		extension = "xlsx"
	else:
		import csv
		from io import StringIO

		buffer = StringIO()
		writer = csv.writer(buffer)
		writer.writerows([fieldnames, *values])
		payload = buffer.getvalue().encode()
		extension = "csv"
	file_doc = save_file(f"{frappe.scrub(report_name)}.{extension}", payload, "Report", report_name, is_private=1)
	return {"success": True, "report_name": report_name, "format": output_format, "file_url": file_doc.file_url, "data_count": len(rows)}
