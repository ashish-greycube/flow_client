# Copyright (C) 2025 Paul Clinton
# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any, Literal

import frappe

from flow.knowledge.extract import extract_file
from flow.lib.tool import tool

MAX_CONTENT_CHARS = 200_000


@tool
def extract_file_content(
	file_url: str,
	operation: Literal["extract", "ocr", "parse_data", "extract_tables"] = "extract",
	max_characters: int = 50_000,
) -> dict[str, Any]:
	"""Extract text, OCR, tables, or spreadsheet content from a permitted Frappe File."""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	frappe.has_permission("File", "read", doc=file_doc, throw=True)
	content = extract_file(file_doc)
	limit = min(max(int(max_characters), 1), MAX_CONTENT_CHARS)
	return {
		"success": True,
		"file": file_doc.name,
		"file_name": file_doc.file_name,
		"operation": operation,
		"content": content[:limit],
		"characters": len(content),
		"truncated": len(content) > limit,
	}
