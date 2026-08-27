# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import math
import json
import re
import statistics
import time
from collections import Counter
from typing import Any, Literal

import frappe

from flow.lib.tool import tool
from flow.utils.safe_exec import safe_exec

MAX_ANALYSIS_ROWS = 10_000
MAX_QUERY_ROWS = 1_000
FORBIDDEN_SQL = re.compile(
	r"\b(?:insert|update|delete|drop|create|alter|truncate|replace|grant|revoke|call|execute|load|outfile|dumpfile|lock|unlock|set)\b",
	re.IGNORECASE,
)


@tool
def analyze_business_data(
	doctype: str,
	analysis_type: Literal["profile", "statistics", "trends", "quality", "correlations"],
	fields: list[str] | None = None,
	filters: dict[str, Any] | None = None,
	date_field: str | None = None,
	limit: int = 1000,
) -> dict[str, Any]:
	"""Profile permitted Frappe records for statistics, trends, quality, or correlations."""
	frappe.has_permission(doctype, "read", throw=True)
	selected = _analysis_fields(doctype, fields)
	rows = [dict(row) for row in frappe.get_list(
		doctype,
		filters=filters or {},
		fields=selected,
		limit=min(max(int(limit), 1), MAX_ANALYSIS_ROWS),
		order_by="creation desc",
	)]
	if not rows:
		return {"success": True, "doctype": doctype, "analysis_type": analysis_type, "record_count": 0, "analysis_result": {}}
	handlers = {
		"profile": _profile,
		"statistics": _statistics,
		"quality": _quality,
		"correlations": _correlations,
		"trends": lambda data: _trends(data, date_field or "creation"),
	}
	return {
		"success": True,
		"doctype": doctype,
		"analysis_type": analysis_type,
		"record_count": len(rows),
		"analysis_result": handlers[analysis_type](rows),
	}


@tool
def run_database_query(
	query: str,
	analysis_type: Literal["basic", "statistical", "detailed"] = "basic",
	validate_query: bool = True,
	format_results: bool = True,
	include_schema_info: bool = False,
	limit: int = 100,
) -> dict[str, Any]:
	"""Run one read-only SELECT query for a System Manager and summarize its result."""
	frappe.only_for("System Manager")
	clean = _validate_select(query)
	limit = min(max(int(limit), 1), MAX_QUERY_ROWS)
	if not re.search(r"\blimit\s+\d+", clean, re.IGNORECASE):
		clean = f"{clean} LIMIT {limit}"
	started = time.perf_counter()
	rows = [dict(row) for row in frappe.db.sql(clean, as_dict=True)]
	response: dict[str, Any] = {
		"success": True,
		"query_executed": clean,
		"rows_returned": len(rows),
		"execution_time_ms": round((time.perf_counter() - started) * 1000, 2),
		"data": rows if format_results else None,
		"analysis": _profile(rows),
	}
	if analysis_type in {"statistical", "detailed"}:
		response["analysis"]["statistics"] = _statistics(rows)
	if include_schema_info:
		response["schema_info"] = {"columns": list(rows[0]) if rows else []}
	if validate_query:
		response["validation"] = {"select_only": True, "single_statement": True}
	return response


@tool(requires_confirmation=True)
def run_python_code(
	code: str,
	data_query: dict[str, Any] | None = None,
	timeout: int = 30,
	capture_output: bool = True,
	return_variables: list[str] | None = None,
) -> dict[str, Any]:
	"""Execute permission-restricted Python in Flow's sandbox; assign the final value to result."""
	frappe.only_for("System Manager")
	if not code.strip():
		raise frappe.ValidationError("Code is required")
	if timeout < 1 or timeout > 300:
		raise frappe.ValidationError("Timeout must be between 1 and 300 seconds")
	injected: dict[str, Any] = {}
	from frappe.utils.safe_exec import NamespaceDict

	from flow.fac_tools.registry import FAC_TOOLS

	injected["tools"] = NamespaceDict(
		**{
			advanced_tool.name: advanced_tool.func
			for advanced_tool in FAC_TOOLS
			if advanced_tool.name not in {"run_python_code", "run_database_query", "create_dashboard", "create_dashboard_chart"}
		}
	)
	if data_query:
		doctype = data_query.get("doctype")
		frappe.has_permission(doctype, "read", throw=True)
		injected["data"] = frappe.get_list(
			doctype,
			fields=data_query.get("fields") or ["name"],
			filters=data_query.get("filters") or {},
			limit=min(int(data_query.get("limit") or 100), MAX_ANALYSIS_ROWS),
		)
	globals_out, _ = safe_exec(code, injected, script_filename="run_python_code")
	variables = {
		name: globals_out.get(name)
		for name in (return_variables or [])
		if name in globals_out and not name.startswith("_")
	}
	return {
		"success": True,
		"result": globals_out.get("result"),
		"output": str(globals_out.get("_print", "")) if capture_output else "",
		"variables": variables,
		"timeout_requested": timeout,
	}


def _analysis_fields(doctype: str, requested: list[str] | None) -> list[str]:
	meta = frappe.get_meta(doctype)
	allowed = {"name", "creation", "modified"} | {field.fieldname for field in meta.fields}
	if requested:
		unknown = set(requested) - allowed
		if unknown:
			raise frappe.ValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")
		return list(dict.fromkeys(["name", *requested]))
	useful = {"Data", "Int", "Float", "Currency", "Percent", "Date", "Datetime", "Check", "Select"}
	return ["name", "creation", "modified", *[field.fieldname for field in meta.fields if field.fieldtype in useful]]


def _profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
	if not rows:
		return {"total_rows": 0, "total_columns": 0, "columns": {}}
	columns = list(rows[0])
	return {
		"total_rows": len(rows),
		"total_columns": len(columns),
		"columns": {
			column: {
				"null_count": sum(row.get(column) in (None, "") for row in rows),
				"unique_count": len({_hashable(row.get(column)) for row in rows}),
			}
			for column in columns
		},
	}


def _statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
	result = {}
	for column in (rows[0] if rows else {}):
		values = [float(row[column]) for row in rows if isinstance(row.get(column), int | float) and not isinstance(row.get(column), bool)]
		if values:
			result[column] = {
				"count": len(values), "min": min(values), "max": max(values), "mean": statistics.fmean(values),
				"median": statistics.median(values), "standard_deviation": statistics.pstdev(values) if len(values) > 1 else 0,
			}
	return result


def _quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
	profile = _profile(rows)
	cell_count = max(profile["total_rows"] * profile["total_columns"], 1)
	nulls = sum(column["null_count"] for column in profile["columns"].values())
	duplicates = len(rows) - len({_hashable(row) for row in rows})
	return {"completeness_percent": round((1 - nulls / cell_count) * 100, 2), "duplicate_rows": duplicates, "field_quality": profile["columns"]}


def _trends(rows: list[dict[str, Any]], date_field: str) -> dict[str, Any]:
	counts: Counter[str] = Counter()
	for row in rows:
		value = row.get(date_field)
		if value:
			counts[str(value)[:7]] += 1
	return {"date_field": date_field, "monthly_counts": dict(sorted(counts.items()))}


def _correlations(rows: list[dict[str, Any]]) -> dict[str, Any]:
	numeric = {column: [row.get(column) for row in rows] for column in (rows[0] if rows else {}) if all(row.get(column) is None or isinstance(row.get(column), int | float) for row in rows)}
	result = {}
	for left, left_values in numeric.items():
		for right, right_values in numeric.items():
			if left >= right:
				continue
			pairs = [(float(a), float(b)) for a, b in zip(left_values, right_values, strict=True) if a is not None and b is not None]
			if len(pairs) > 1:
				result[f"{left}__{right}"] = _pearson(pairs)
	return result


def _pearson(pairs: list[tuple[float, float]]) -> float:
	xs, ys = zip(*pairs, strict=True)
	x_mean, y_mean = statistics.fmean(xs), statistics.fmean(ys)
	numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
	denominator = math.sqrt(sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys))
	return round(numerator / denominator, 6) if denominator else 0.0


def _validate_select(query: str) -> str:
	clean = re.sub(r"--[^\n]*|/\*.*?\*/", " ", query, flags=re.DOTALL).strip().rstrip(";")
	if not clean.lower().startswith(("select ", "with ")) or FORBIDDEN_SQL.search(clean):
		raise frappe.PermissionError("Only one read-only SELECT query is allowed")
	if ";" in clean:
		raise frappe.PermissionError("Multiple SQL statements are not allowed")
	return clean


def _hashable(value: Any) -> str:
	return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))
