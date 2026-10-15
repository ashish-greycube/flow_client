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
# aggregate / duplicates / field_changes return at most this many groups or changes, and a
# duplicate group lists at most this many of its records: the model needs the largest findings
# and evidence for each, not every member of a recurring 40-invoice pattern.
MAX_RESULT_GROUPS = 100
MAX_GROUP_RECORDS = 10
# duplicates and field_changes compare in Python, over at most this many records.
MAX_SCAN_ROWS = 50_000
AGGREGATE_FUNCTIONS = {"sum": "SUM", "count": "COUNT", "avg": "AVG", "min": "MIN", "max": "MAX"}
STANDARD_FIELDS = frozenset({"name", "owner", "creation", "modified", "modified_by", "docstatus", "parent", "parenttype", "idx"})
FORBIDDEN_SQL = re.compile(
	r"\b(?:insert|update|delete|drop|create|alter|truncate|replace|grant|revoke|call|execute|load|outfile|dumpfile|lock|unlock|set)\b",
	re.IGNORECASE,
)


@tool
def analyze_business_data(
	doctype: str,
	analysis_type: Literal[
		"profile", "statistics", "trends", "quality", "correlations", "aggregate", "duplicates", "field_changes"
	],
	fields: list[str] | None = None,
	filters: dict[str, Any] | None = None,
	date_field: str | None = None,
	limit: int = 1000,
	group_by: list[str] | None = None,
	aggregates: list[str] | None = None,
	order_by: str | None = None,
	within_days: int | None = None,
	since: str | None = None,
	parent_doctype: str | None = None,
) -> dict[str, Any]:
	"""Analyze permitted Frappe records on the server, across every matching record.

	- profile / statistics / trends / quality / correlations: summaries of up to `limit` records.
	- aggregate: totals per group, e.g. outstanding per customer or last movement per item.
	  `group_by` fields, `aggregates` like ["sum:paid_amount", "count", "max:posting_date"],
	  optional `order_by` (e.g. "sum_paid_amount desc"); returns at most `limit` groups.
	- duplicates: groups of records whose `fields` match (text compared ignoring case and spacing),
	  e.g. Payment Entry on ["party", "paid_amount"] with date_field "posting_date" and
	  within_days 7, Supplier on ["tax_id"], Bank Account on ["bank_account_no"], or Payment Entry
	  Reference on ["reference_name"] (an invoice paid twice).
	- field_changes: edits to `fields` of `doctype` from its change history since `since`
	  (default 90 days ago), e.g. Bank Account ["bank_account_no", "branch_code"].
	Child tables are read through their parent; pass `parent_doctype` if there are several."""
	if analysis_type in ("aggregate", "duplicates", "field_changes"):
		return _record_analysis(
			doctype, analysis_type, fields, filters, date_field, limit, group_by, aggregates,
			order_by, within_days, since, parent_doctype,
		)
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


def _record_analysis(
	doctype, analysis_type, fields, filters, date_field, limit, group_by, aggregates, order_by,
	within_days, since, parent_doctype,
) -> dict[str, Any]:
	from flow.tools.builtins import child_table_scope

	filters, parent = child_table_scope(doctype, filters or {}, parent_doctype)
	frappe.has_permission(parent or doctype, "read", throw=True)
	limit = min(max(int(limit or 1), 1), MAX_RESULT_GROUPS)
	result: dict[str, Any] = {"success": True, "doctype": doctype, "analysis_type": analysis_type}
	if analysis_type == "aggregate":
		result.update(_aggregate(doctype, filters, group_by or [], aggregates or ["count"], order_by, limit, parent))
	elif analysis_type == "duplicates":
		result.update(_duplicates(doctype, filters, fields, date_field, within_days, limit, parent))
	else:
		result.update(_field_changes(doctype, fields, since, limit))
	return result


def _aggregate(doctype, filters, group_by, aggregates, order_by, limit, parent) -> dict[str, Any]:
	"""Totals per group, computed by the database over every permitted record."""
	_check_fields(doctype, group_by)
	columns, aliases = [], []
	for spec in aggregates:
		function, _, field = spec.partition(":")
		function = function.strip().lower()
		if function not in AGGREGATE_FUNCTIONS:
			raise frappe.ValidationError(f"Unknown aggregate {spec!r}; use sum, count, avg, min or max.")
		if function == "count" and not field:
			columns.append({"COUNT": "*", "as": "count"})
			aliases.append("count")
			continue
		_check_fields(doctype, [field])
		alias = f"{function}_{field}"
		columns.append({AGGREGATE_FUNCTIONS[function]: field, "as": alias})
		aliases.append(alias)
	order = _aggregate_order(order_by, aliases, group_by)
	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=[*group_by, *columns],
		group_by=", ".join(group_by) or None,
		order_by=order,
		limit=limit + 1,
		parent_doctype=parent,
	)
	result = {"group_by": group_by, "rows": rows[:limit], "groups_returned": min(len(rows), limit)}
	if len(rows) > limit:
		result["has_more"] = True
		result["note"] = f"More than {limit} groups; these are the first {limit} by {order}. Raise limit or narrow filters."
	return result


def _aggregate_order(order_by: str | None, aliases: list[str], group_by: list[str]) -> str:
	if not order_by:
		return f"{aliases[0]} desc"
	column, _, direction = order_by.strip().partition(" ")
	direction = (direction.strip() or "desc").lower()
	if column not in {*aliases, *group_by} or direction not in ("asc", "desc"):
		raise frappe.ValidationError(f"order_by must be one of {', '.join([*aliases, *group_by])} followed by asc or desc.")
	return f"{column} {direction}"


def _duplicates(doctype, filters, fields, date_field, within_days, limit, parent) -> dict[str, Any]:
	"""Groups of permitted records whose `fields` match, optionally only within `within_days`
	of each other on `date_field`. Compared in Python, over every record up to MAX_SCAN_ROWS."""
	if not fields:
		raise frappe.ValidationError("duplicates needs `fields` to match on.")
	_check_fields(doctype, [*fields, *([date_field] if date_field else [])])
	extra = ["parent"] if parent else []
	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=list(dict.fromkeys(["name", *extra, *fields, *([date_field] if date_field else [])])),
		order_by=f"{date_field} asc" if date_field else "creation asc",
		limit=MAX_SCAN_ROWS + 1,
		parent_doctype=parent,
	)
	scanned = rows[:MAX_SCAN_ROWS]
	groups: dict[tuple, list[dict]] = {}
	for row in scanned:
		key = tuple(_match_value(row.get(f)) for f in fields)
		if any(value in (None, "") for value in key):
			continue
		groups.setdefault(key, []).append(row)
	found = []
	for members in groups.values():
		for cluster in _date_clusters(members, date_field, within_days):
			if len(cluster) > 1:
				found.append(cluster)
	found.sort(key=len, reverse=True)
	result = {
		"match_fields": fields,
		"records_scanned": len(scanned),
		"duplicate_groups": len(found),
		"groups": [_duplicate_group(cluster, fields, date_field, parent) for cluster in found[:limit]],
	}
	if len(found) > limit:
		result["has_more"] = True
		result["note"] = f"{len(found)} groups found; showing the {limit} largest. Raise limit or narrow filters."
	if len(rows) > MAX_SCAN_ROWS:
		result["has_more"] = True
		result["note"] = f"Only the first {MAX_SCAN_ROWS} records were compared; narrow the filters to cover the rest."
	return result


def _match_value(value: Any) -> Any:
	if isinstance(value, str):
		# Imported data carries Excel's "_x000D_" carriage returns and stray spacing.
		return " ".join(value.replace("_x000D_", " ").split()).casefold()
	if isinstance(value, float):
		return round(value, 2)
	return value


def _date_clusters(members: list[dict], date_field: str | None, within_days: int | None) -> list[list[dict]]:
	"""Split one group into runs whose consecutive dates are at most `within_days` apart."""
	if not date_field or within_days is None:
		return [members]
	ordered = sorted(members, key=lambda row: str(row.get(date_field) or ""))
	clusters, current, previous = [], [], None
	for row in ordered:
		date = frappe.utils.getdate(row.get(date_field)) if row.get(date_field) else None
		if current and (date is None or previous is None or (date - previous).days > within_days):
			clusters.append(current)
			current = []
		current.append(row)
		previous = date
	if current:
		clusters.append(current)
	return clusters


def _duplicate_group(cluster: list[dict], fields: list[str], date_field: str | None, parent: str | None) -> dict[str, Any]:
	group: dict[str, Any] = {
		"match": {f: cluster[0].get(f) for f in fields},
		"count": len(cluster),
		"records": [row["name"] for row in cluster[:MAX_GROUP_RECORDS]],
	}
	if parent:
		group["parents"] = list(dict.fromkeys(row["parent"] for row in cluster))[:MAX_GROUP_RECORDS]
	if date_field:
		group["dates"] = [row.get(date_field) for row in cluster[:MAX_GROUP_RECORDS]]
	return group


def _field_changes(doctype, fields, since, limit) -> dict[str, Any]:
	"""Edits to `fields` of `doctype` from its Version history, newest first, for records the
	user may read."""
	if fields:
		_check_fields(doctype, fields)
	since = since or frappe.utils.add_days(frappe.utils.nowdate(), -90)
	versions = frappe.get_list(
		"Version",
		filters={"ref_doctype": doctype, "creation": [">=", since]},
		fields=["docname", "owner", "creation", "data"],
		order_by="creation desc",
		limit=MAX_SCAN_ROWS,
	)
	wanted = set(fields or [])
	readable: dict[str, bool] = {}
	changes = []
	for version in versions:
		if version.docname not in readable:
			readable[version.docname] = bool(frappe.has_permission(doctype, "read", version.docname))
		if not readable[version.docname]:
			continue
		try:
			changed = json.loads(version.data or "{}").get("changed") or []
		except (TypeError, ValueError):
			continue
		for field, old, new in (c for c in changed if isinstance(c, list) and len(c) == 3):
			if wanted and field not in wanted:
				continue
			changes.append(
				{"docname": version.docname, "field": field, "old": old, "new": new,
				 "changed_by": version.owner, "changed_at": version.creation}
			)
	result = {"since": str(since), "fields": fields or "all", "changes_found": len(changes), "changes": changes[:limit]}
	if len(changes) > limit:
		result["has_more"] = True
		result["note"] = f"{len(changes)} changes found; showing the {limit} newest. Raise limit or narrow `fields`/`since`."
	return result


def _check_fields(doctype: str, fields: list[str]) -> None:
	"""Only real fields of `doctype` may be grouped, aggregated or compared."""
	meta = frappe.get_meta(doctype)
	unknown = [f for f in fields if f not in STANDARD_FIELDS and not meta.has_field(f)]
	if unknown:
		raise frappe.ValidationError(f"Unknown fields for {doctype}: {', '.join(unknown)}")


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
		raise frappe.ValidationError("Only one read-only SELECT query is allowed")
	if ";" in clean:
		raise frappe.ValidationError("Multiple SQL statements are not allowed")
	return clean


def _hashable(value: Any) -> str:
	return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))
