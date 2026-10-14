# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any, Literal

import frappe

from flow.fac_tools import prepared_reports
from flow.fac_tools.report_filters import apply_defaults, discover_filters
from flow.lib.tool import tool

MAX_REPORT_ROWS = 500
# Seconds one query of an inline report may run before the report moves to the background.
INLINE_QUERY_TIMEOUT = 90
SUMMABLE_FIELDTYPES = {"Currency", "Float", "Int"}


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
	sort_by: str | None = None,
	sort_order: Literal["desc", "asc"] = "desc",
	limit: int | None = None,
) -> dict[str, Any]:
	"""Execute a permitted Script, Query, or Custom Report and return at most 500 rows, with
	column_totals computed over all rows. Call report_requirements first and pass the
	report's own filter names. For "top N", "highest", "lowest" or "largest" questions, pass
	sort_by (a column fieldname, e.g. "outstanding") and limit (N): the whole report is
	sorted on the server and only those rows are returned, so never sort rows yourself or
	export the report to rank them. A heavy (prepared) report may run in the background:
	`status` is then ready, generating, started, or failed. Never call this again for the
	same report in the same reply while it is generating or started: tell the user and end
	the reply. A failed result gives the reason; correct the filters before retrying."""
	report = _report(report_name)
	if report.report_type == "Report Builder":
		raise frappe.ValidationError("Report Builder reports are not supported by this tool")

	definitions = [_filter_dict(row) for row in (report.filters or [])]
	if not definitions:
		definitions, _ = discover_filters(report.name)
	applied = apply_defaults(filters or {}, definitions)
	response = None
	if prepared_reports.is_prepared(report.name):
		response = prepared_reports.handle(report.name, applied, definitions)
	if response is None:
		response = _run_inline(report.name, applied, definitions)
	if response.get("status") in {"started", "generating", "failed"}:
		return response
	output = response.get("output", response)

	data = [dict(row) if isinstance(row, dict) else row for row in (output.get("result") or [])]
	columns = output.get("columns") or []
	rows = sort_rows(columns, data, sort_by, sort_order) if sort_by else data
	shown = min(_row_limit(limit), len(rows))
	if format != "json":
		frappe.permissions.can_export(report.ref_doctype, raise_exception=True)
		return _export(report.name, columns, rows[:shown] if limit else rows, format)

	result = {
		"success": True,
		"report_name": report.name,
		"report_type": report.report_type,
		"data": rows[:shown],
		"data_count": len(data),
		"truncated": shown < len(rows),
		"column_totals": column_totals(columns, data),
		"columns": columns,
		"message": output.get("message"),
		"chart": output.get("chart"),
		"report_summary": output.get("report_summary"),
		"filters_applied": applied,
	}
	if sort_by:
		result["sorted_by"] = f"{_sort_field(columns, sort_by)} {sort_order}"
	if shown < len(rows):
		order = f"sorted by {result['sorted_by']}" if sort_by else "in report order"
		result["row_note"] = (
			f"Showing {shown} of {len(rows)} rows, {order}; column_totals cover all rows. "
			"Use sort_by and limit to get the rows a question needs, or format='excel' for every row."
		)
	if response.get("status") == "ready":
		result.update(status="ready", as_of=response["as_of"], prepared_report_run=response["run"])
	return result


def sort_rows(columns: list, rows: list, sort_by: str, sort_order: str = "desc") -> list:
	"""The report's data rows ordered by one column, empty values last. The report's own
	total row (a list) is left out, and a tree report can't be sorted without breaking its
	nesting."""
	if any(isinstance(row, dict) and "indent" in row for row in rows):
		raise frappe.ValidationError(
			"This report is a tree (rows nest under each other), so it cannot be sorted. "
			"Run it without sort_by."
		)
	fieldname = _sort_field(columns, sort_by)
	records = [row for row in rows if isinstance(row, dict)]
	filled = [row for row in records if row.get(fieldname) not in (None, "")]
	empty = [row for row in records if row.get(fieldname) in (None, "")]
	numeric = all(isinstance(row[fieldname], int | float) for row in filled)
	filled.sort(
		key=lambda row: row[fieldname] if numeric else str(row[fieldname]).casefold(),
		reverse=sort_order == "desc",
	)
	return filled + empty


def _sort_field(columns: list, sort_by: str) -> str:
	"""The fieldname `sort_by` names, matched on fieldname or label, ignoring case."""
	wanted = sort_by.strip().casefold()
	for column in columns:
		if not isinstance(column, dict):
			continue
		if wanted in {str(column.get("fieldname") or "").casefold(), str(column.get("label") or "").casefold()}:
			return column["fieldname"]
	names = [column.get("fieldname") for column in columns if isinstance(column, dict) and column.get("fieldname")]
	raise frappe.ValidationError(f"Unknown sort_by column {sort_by!r}. Columns: {', '.join(names)}")


def _row_limit(limit: int | None) -> int:
	if limit is None:
		return MAX_REPORT_ROWS
	if limit < 1:
		raise frappe.ValidationError("limit must be at least 1")
	return min(limit, MAX_REPORT_ROWS)


def column_totals(columns: list, rows: list) -> dict[str, Any] | None:
	"""Sum each Currency, Float, and Int column over every row, so the model gets totals
	without adding up rows. None for a tree report, whose nested rows would count twice.
	The report's own total row is a list, not a dict, so it is never summed."""
	if any(isinstance(row, dict) and "indent" in row for row in rows):
		return None
	records = [row for row in rows if isinstance(row, dict)]
	currencies = {row.get("currency") for row in records if row.get("currency")}
	totals = {}
	for column in columns:
		if not isinstance(column, dict) or column.get("fieldtype") not in SUMMABLE_FIELDTYPES:
			continue
		# Rows in different currencies have no meaningful money total.
		if column["fieldtype"] == "Currency" and len(currencies) > 1:
			continue
		values = [row.get(column.get("fieldname")) for row in records]
		totals[column.get("fieldname")] = round(sum(value for value in values if isinstance(value, int | float)), 6)
	return totals


def _run_inline(report_name: str, filters: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
	"""Run the report in this turn. A single query running past INLINE_QUERY_TIMEOUT is
	killed, and the report moves to a background run instead of holding the turn."""
	from frappe.database.database import get_query_execution_timeout
	from frappe.desk.query_report import run

	frappe.db.set_execution_timeout(INLINE_QUERY_TIMEOUT)
	try:
		return run(
			report_name=report_name,
			filters=filters,
			user=frappe.session.user,
			ignore_prepared_report=True,
			js_filters=definitions,
		)
	except Exception as e:
		if not frappe.db.is_statement_timeout(e):
			raise
		if not prepared_reports.worker_available():
			raise frappe.ValidationError(
				"This report is too heavy to run inline and no background worker is running to "
				"generate it. Narrow the filters, or ask an administrator to start the workers."
			) from e
		_mark_prepared(report_name)
		return prepared_reports.start(
			report_name,
			filters,
			"This report took too long to run inline, so it now runs in the background and has "
			"been started.",
		)
	finally:
		frappe.db.set_execution_timeout(get_query_execution_timeout())


def _mark_prepared(report_name: str) -> None:
	"""Flag a slow report as prepared, as Frappe does for a slow Script Report, so the
	next ask finds the background run instead of timing out again."""
	if not frappe.db.get_value("Report", report_name, "disable_prepared_report_automation"):
		frappe.db.set_value("Report", report_name, "prepared_report", 1)


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
