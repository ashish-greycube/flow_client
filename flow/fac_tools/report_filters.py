# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe.utils import add_months, today

_STRING = r'["\'`]((?:[^"\'`\\]|\\.)*)["\'`]'
# A filters array: `filters: [` in a report object, or `let filters = [` in a shared builder.
_FILTERS_ARRAY = re.compile(r"\bfilters\s*[:=]\s*\[")
# Filters a report adds to a shared set: `frappe.query_reports[name]["filters"].push(`.
_FILTERS_PUSH = re.compile(r"""(?:\[\s*["']filters["']\s*\]|\.filters)\s*\.push\s*\(""")
# Shared filter builders that reports copy in with `$.extend({}, <object>)`, by the object
# the report script names and the file (app, path) that defines its filters.
SHARED_FILTER_SCRIPTS = {
	"erpnext.financial_statements": ("erpnext", "public/js/financial_statements.js"),
}


def discover_filters(report_name: str) -> tuple[list[dict[str, Any]], list[str]]:
	"""Extract the common declarative query-report filter syntax from rendered JS: the
	report's own filters array, the filters of a shared builder it copies in (such as
	ERPNext's financial statements), and the filters it pushes onto them."""
	from frappe.desk.query_report import get_script

	script = get_script(report_name).get("script") or ""
	filters = _array_filters(script) + _shared_filters(script) + _pushed_filters(script)
	if not filters:
		return [], ["No declarative filters array was found in the report script."]
	unique = {}
	for definition in filters:
		unique.setdefault(definition["fieldname"], definition)
	return list(unique.values()), []


def _array_filters(script: str) -> list[dict[str, Any]]:
	match = _FILTERS_ARRAY.search(script)
	if not match:
		return []
	start = script.find("[", match.start())
	end = _matching(script, start, "[", "]")
	return _definitions(script[start + 1 : end]) if end > 0 else []


def _shared_filters(script: str) -> list[dict[str, Any]]:
	filters = []
	for name, (app, path) in SHARED_FILTER_SCRIPTS.items():
		if name not in script or app not in frappe.get_installed_apps():
			continue
		try:
			with open(frappe.get_app_path(app, *path.split("/")), encoding="utf-8") as source:
				filters += _array_filters(source.read())
		except OSError:
			continue
	return filters


def _pushed_filters(script: str) -> list[dict[str, Any]]:
	filters = []
	for match in _FILTERS_PUSH.finditer(script):
		start = match.end() - 1
		end = _matching(script, start, "(", ")")
		if end > 0:
			filters += _definitions(script[start + 1 : end])
	return filters


def _definitions(text: str) -> list[dict[str, Any]]:
	filters = []
	for block in _object_blocks(text):
		fieldname = _string_property(block, "fieldname")
		if not fieldname:
			continue
		fieldtype = _string_property(block, "fieldtype") or "Data"
		definition: dict[str, Any] = {
			"fieldname": fieldname,
			"label": _label_property(block) or frappe.unscrub(fieldname),
			"fieldtype": fieldtype,
			"required": bool(_scalar_property(block, "reqd")),
		}
		required_when = re.search(r"""\bmandatory_depends_on\s*:\s*(["'`])(.*?)\1""", block)
		if required_when:
			definition["required_when"] = required_when.group(2).removeprefix("eval:").strip()
		options = _options_property(block, fieldtype)
		if options is not None:
			definition["options"] = options
		default, expression = _default_property(block)
		if default is not None:
			definition["default"] = default
		elif expression:
			definition["default_expression"] = expression
		filters.append(definition)
	return filters


def apply_defaults(filters: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
	result = dict(filters)
	for definition in definitions:
		if definition["fieldname"] not in result and "default" in definition:
			result[definition["fieldname"]] = definition["default"]
	missing = []
	for definition in definitions:
		fieldname = definition["fieldname"]
		if result.get(fieldname) not in (None, "", []):
			continue
		if definition.get("required"):
			missing.append(fieldname)
		elif _condition_met(definition.get("required_when"), result):
			missing.append(f"{fieldname} (required when {definition['required_when']})")
	if missing:
		raise frappe.ValidationError(
			"Missing required report filters: " + ", ".join(missing) + ". Call report_requirements first."
		)
	return result


def _condition_met(expression: str | None, filters: dict[str, Any]) -> bool:
	"""Evaluate a simple `doc.<field> == '<value>'` condition; anything else reads as unmet."""
	match = re.fullmatch(r"""doc\.(\w+)\s*===?\s*["'](.*)["']""", (expression or "").strip())
	return bool(match) and str(filters.get(match.group(1))) == match.group(2)


def _object_blocks(text: str) -> list[str]:
	blocks = []
	index = 0
	while index < len(text):
		if text[index] != "{":
			index += 1
			continue
		end = _matching(text, index, "{", "}")
		if end < 0:
			break
		blocks.append(text[index + 1 : end])
		index = end + 1
	return blocks


def _matching(text: str, start: int, opener: str, closer: str) -> int:
	depth = 0
	quote = None
	escaped = False
	for index in range(start, len(text)):
		char = text[index]
		if quote:
			if escaped:
				escaped = False
			elif char == "\\":
				escaped = True
			elif char == quote:
				quote = None
			continue
		if char in {'"', "'", "`"}:
			quote = char
		elif char == opener:
			depth += 1
		elif char == closer:
			depth -= 1
			if depth == 0:
				return index
	return -1


def _string_property(block: str, name: str) -> str | None:
	match = re.search(rf"\b{re.escape(name)}\s*:\s*{_STRING}", block)
	return _unescape(match.group(1)) if match else None


def _label_property(block: str) -> str | None:
	match = re.search(rf"\blabel\s*:\s*(?:__\(\s*)?{_STRING}", block)
	return _unescape(match.group(1)) if match else None


def _scalar_property(block: str, name: str) -> Any:
	match = re.search(rf"\b{re.escape(name)}\s*:\s*(true|false|-?\d+(?:\.\d+)?)", block)
	if not match:
		return None
	value = match.group(1)
	if value in {"true", "false"}:
		return value == "true"
	return float(value) if "." in value else int(value)


def _options_property(block: str, fieldtype: str) -> str | list[str] | None:
	string_value = _string_property(block, "options")
	if string_value is not None:
		if fieldtype in {"Select", "Autocomplete"}:
			return [value.strip() for value in string_value.replace("\\n", "\n").splitlines() if value.strip()]
		return string_value
	match = re.search(r"\boptions\s*:\s*\[", block)
	if not match:
		return None
	start = block.find("[", match.start())
	end = _matching(block, start, "[", "]")
	if end < 0:
		return None
	array = block[start + 1 : end]
	values = re.findall(rf"\bvalue\s*:\s*{_STRING}", array)
	if values:
		return [_unescape(value) for value in values]
	return [_unescape(value) for value in re.findall(_STRING, array)]


def _default_property(block: str) -> tuple[Any, str | None]:
	string_value = _string_property(block, "default")
	if string_value is not None:
		return string_value, None
	scalar = _scalar_property(block, "default")
	if scalar is not None:
		return scalar, None
	expression = _property_expression(block, "default")
	if not expression:
		return None, None
	# A Select default written as a one-item list, e.g. `default: ["Fiscal Year"]`.
	single = re.fullmatch(rf"\[\s*{_STRING}\s*\]", expression)
	if single:
		return _unescape(single.group(1)), None
	user_default = re.search(r"frappe\.defaults\.get_user_default\([\"']([^\"']+)", expression)
	if user_default:
		return frappe.defaults.get_user_default(user_default.group(1)), expression
	if "frappe.datetime.get_today()" in expression:
		months = re.search(r"add_months\([^,]+,\s*(-?\d+)\)", expression)
		return (str(add_months(today(), int(months.group(1)))) if months else today()), expression
	return None, expression


def _property_expression(block: str, name: str) -> str | None:
	match = re.search(rf"\b{re.escape(name)}\s*:\s*", block)
	if not match:
		return None
	start = match.end()
	depth = 0
	quote = None
	escaped = False
	for index in range(start, len(block)):
		char = block[index]
		if quote:
			if escaped:
				escaped = False
			elif char == "\\":
				escaped = True
			elif char == quote:
				quote = None
			continue
		if char in {'"', "'", "`"}:
			quote = char
		elif char in "([{":
			depth += 1
		elif char in ")]}" and depth:
			depth -= 1
		elif char == "," and depth == 0:
			return block[start:index].strip()
	return block[start:].strip() or None


def _unescape(value: str) -> str:
	return value.replace(r"\'", "'").replace(r'\"', '"').replace(r"\\n", "\n")
