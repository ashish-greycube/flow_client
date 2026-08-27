# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe.utils import add_months, today

_STRING = r'["\'`]((?:[^"\'`\\]|\\.)*)["\'`]'


def discover_filters(report_name: str) -> tuple[list[dict[str, Any]], list[str]]:
	"""Extract the common declarative query-report filter syntax from rendered JS."""
	from frappe.desk.query_report import get_script

	script = get_script(report_name).get("script") or ""
	match = re.search(r"\bfilters\s*:\s*\[", script)
	if not match:
		return [], ["No declarative filters array was found in the report script."]
	start = script.find("[", match.start())
	end = _matching(script, start, "[", "]")
	if end < 0:
		return [], ["The report filters array could not be parsed."]
	filters = []
	for block in _object_blocks(script[start + 1 : end]):
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
		options = _options_property(block, fieldtype)
		if options is not None:
			definition["options"] = options
		default, expression = _default_property(block)
		if default is not None:
			definition["default"] = default
		elif expression:
			definition["default_expression"] = expression
		filters.append(definition)
	return filters, []


def apply_defaults(filters: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
	result = dict(filters)
	missing = []
	for definition in definitions:
		fieldname = definition["fieldname"]
		if fieldname not in result and "default" in definition:
			result[fieldname] = definition["default"]
		if definition.get("required") and result.get(fieldname) in (None, "", []):
			missing.append(fieldname)
	if missing:
		raise frappe.ValidationError(
			"Missing required report filters: " + ", ".join(missing) + ". Call report_requirements first."
		)
	return result


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
