# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Cap the size of a tool result before it reaches the model, adapted from Jarvis.

Every tool result stays in the transcript and is re-sent on each later model call, so
one oversized result slows down and inflates every remaining step of the turn. A
result over MAX_RESULT_CHARS keeps the longest prefix of its row list that fits and
says plainly that the rows are partial.
"""

from __future__ import annotations

import json
from typing import Any

# About 9K tokens.
MAX_RESULT_CHARS = 35_000
# Top-level list keys that hold rows in Flow's tool results. A bare list is rows too.
ROW_KEYS = ("data", "result", "rows", "results", "reports", "groups", "changes")
# Keys the cap owns in a truncated result; a tool's own key of the same name is dropped.
META_KEYS = ("_truncated", "shown", "total", "note")
# Room for the digits of the note and separators.
SAFETY = 200

NOTE = (
	"Result truncated to fit the context window: showing the first {shown} of {total} rows. "
	"PARTIAL - do not treat as complete; any count, sum, file, or summary built from these "
	"rows is partial too. For the full answer narrow the filters, aggregate in the query, use "
	"the result's own totals (e.g. column_totals), or export the data to a file."
)
NOTE_NONE = (
	"Result too large: even one row exceeds the size budget. Request fewer fields, narrow the "
	"filters, or aggregate in the query."
)
NOTE_NONROW = (
	"Result too large: the content around the rows alone exceeds the size budget, so all "
	"rows were dropped. PARTIAL, showing zero rows. Narrow the request."
)


def fit_result(result: Any) -> Any:
	"""Return `result`, or a truncated copy when its JSON is over MAX_RESULT_CHARS.
	A result with no row list to cut is returned unchanged."""
	try:
		size = _size(result)
	except (TypeError, ValueError):
		return result
	if size <= MAX_RESULT_CHARS:
		return result

	key, rows = _rows(result)
	if rows is None:
		return result
	overhead = _size(_truncated(result, key, [], len(rows), NOTE_NONE))
	budget = MAX_RESULT_CHARS - overhead - SAFETY
	if budget <= 0:
		return _truncated(result, key, [], len(rows), NOTE_NONROW)
	kept = _fit(rows, budget)
	note = NOTE.format(shown=len(kept), total=len(rows)) if kept else NOTE_NONE
	return _truncated(result, key, kept, len(rows), note)


def _size(value: Any) -> int:
	# Serialized exactly as agent._serialize_tool_result does, so the cap measures what the model gets.
	return len(json.dumps(value, default=str))


def _rows(result: Any) -> tuple[str | None, list | None]:
	if isinstance(result, list):
		return None, result
	if isinstance(result, dict):
		for key in ROW_KEYS:
			if isinstance(result.get(key), list):
				return key, result[key]
	return None, None


def _fit(rows: list, budget: int) -> list:
	"""The longest prefix of `rows` that fits in `budget`. Size grows with the prefix,
	so binary search finds it, and a small first row is kept even when later rows are huge."""
	low, high = 0, len(rows)
	while low < high:
		middle = (low + high + 1) // 2
		if _size(rows[:middle]) <= budget:
			low = middle
		else:
			high = middle - 1
	return rows[:low]


def _truncated(result: Any, key: str | None, kept: list, total: int, note: str) -> dict[str, Any]:
	# Metadata first, so it survives when a UI shows only the start of the result.
	out: dict[str, Any] = {"_truncated": True, "shown": len(kept), "total": total, "note": note}
	if key is None:
		out["rows"] = kept
		return out
	for name, value in result.items():
		if name != key and name not in META_KEYS:
			out[name] = value
	out[key] = kept
	return out
