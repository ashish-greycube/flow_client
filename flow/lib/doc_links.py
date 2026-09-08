# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Deterministic safety net for clickable document links: the system prompt (see
DOCUMENT_LINK_INSTRUCTIONS in flow.flow.doctype.flow_agent.flow_agent) asks the model
to format document mentions as Markdown links itself, but that's best-effort. This
module catches whatever it missed by rewriting mentions of any document the run's own
tool calls actually touched — so a name the agent created, read, updated, or acted on
via run_action/describe always ends up linked, even if the model forgot to."""

from __future__ import annotations

import json
import re
from typing import Any

from frappe.utils import get_absolute_url

_REFERENCE_TOOLS = frozenset({"create", "update", "read", "describe", "run_action"})
# Existing Markdown links and code spans are left untouched (shielded before substitution).
_SHIELD_PATTERN = re.compile(r"`[^`]*`|\[[^\]]*\]\([^)]*\)")
_SHIELD_TOKEN = re.compile(r"\x00(\d+)\x00")


def collect_document_references(messages: list[dict[str, Any]]) -> dict[str, str]:
	"""Walk a run's transcript and return {name: doctype} for every record touched by a
	create/update/read/describe/run_action call in it."""
	calls_by_id: dict[str, dict[str, Any]] = {}
	for message in messages:
		if message.get("role") != "assistant":
			continue
		for call in message.get("tool_calls") or []:
			fn = call.get("function") or {}
			if fn.get("name") not in _REFERENCE_TOOLS:
				continue
			try:
				arguments = json.loads(fn.get("arguments") or "{}")
			except (TypeError, ValueError):
				continue
			calls_by_id[call.get("id")] = {"tool": fn["name"], "arguments": arguments}

	references: dict[str, str] = {}
	for message in messages:
		if message.get("role") != "tool":
			continue
		call = calls_by_id.get(message.get("tool_call_id"))
		if not call:
			continue
		try:
			result = json.loads(message.get("content") or "null")
		except (TypeError, ValueError):
			continue
		doctype = call["arguments"].get("doctype")
		if not doctype:
			continue
		for name in _names_from_result(call["tool"], result):
			references[str(name)] = doctype
	return references


def _names_from_result(tool_name: str, result: Any) -> list[Any]:
	if tool_name == "read":
		if isinstance(result, list):
			return [row.get("name") for row in result if isinstance(row, dict) and row.get("name")]
		return []
	if not isinstance(result, dict):
		return []
	if tool_name == "create":
		return result.get("created") or []
	if tool_name == "update":
		return result.get("updated") or []
	if tool_name == "describe":
		return [result["name"]] if result.get("name") else []
	if tool_name == "run_action":
		return [row.get("name") for row in result.get("results") or [] if row.get("name")]
	return []


def linkify_document_mentions(text: str | None, references: dict[str, str]) -> str | None:
	"""Wrap bare mentions of `references`' names in `text` with a Markdown link to the
	record, skipping any already inside a Markdown link or code span."""
	if not text or not references:
		return text

	names = sorted({n for n in references if n}, key=len, reverse=True)
	if not names:
		return text
	mention_pattern = re.compile(
		r"(?<![\w/-])(" + "|".join(re.escape(name) for name in names) + r")(?![\w-])"
	)

	shielded_spans: list[str] = []

	def _shield(match: re.Match) -> str:
		shielded_spans.append(match.group(0))
		return f"\x00{len(shielded_spans) - 1}\x00"

	shielded_text = _SHIELD_PATTERN.sub(_shield, text)

	def _link(match: re.Match) -> str:
		name = match.group(1)
		return f"[{name}]({get_absolute_url(references[name], name)})"

	linked_text = mention_pattern.sub(_link, shielded_text)
	return _SHIELD_TOKEN.sub(lambda m: shielded_spans[int(m.group(1))], linked_text)
