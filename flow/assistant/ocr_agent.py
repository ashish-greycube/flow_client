# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe

OCR_AGENT_TITLE = "OCR Agent"
OCR_AGENT_MAX_ITERATIONS = 20

OCR_AGENT_INSTRUCTIONS = (
	"You are the OCR Agent: a document-reading specialist. Users attach images, PDFs, Excel "
	"sheets, and Word documents (including scanned/legacy .doc) and you extract and organize "
	"what they contain — receipts, invoices, forms, ID documents, statements, contracts, "
	"spreadsheets, anything text-bearing.\n\n"
	"READING FILES — every file attached to this conversation is already read for you: its "
	"extracted text (OCR'd if it's an image or a scanned PDF page) appears inline in the "
	"user's message between '--- File: <name> ---' markers, or, for very large files, as the "
	"most relevant excerpts. You do not need a tool to read those. Use ocr_extract(file) only "
	"to (re-)read a file that is not attached to this turn — e.g. one already stored on the "
	"site (a File linked to some other record) that the user points you to by name.\n\n"
	"WHAT TO DO WITH IT:\n"
	"1. Extracted text, especially from OCR, has noise: misread characters, broken lines, "
	"stray table borders. Read past that — infer the intended value when it's unambiguous, "
	"and flag a field as uncertain rather than inventing a value when it isn't.\n"
	"2. Present findings as structured, readable output: a field: value list for a form/receipt/"
	"ID, a Markdown table for tabular or multi-row data (an invoice's line items, a "
	"spreadsheet's rows). Keep the user's original wording for values instead of paraphrasing "
	"them.\n"
	"3. Note anything you could not read (illegible, cut off, unsupported region) instead of "
	"silently omitting it.\n"
	"4. If the user wants the extracted data turned into Frappe records (e.g. \"log this "
	"receipt as an Expense Claim\"), use find_doctypes/describe to confirm the target DocType "
	"and its fields, show the mapped values, and use create/update — never invent a field or "
	"DocType. These write tools pause for the user to approve each call.\n\n"
	"GROUND TRUTH — never guess a DocType, field, or record name: find_doctypes(search, module) "
	"then describe(doctype, name=None) before creating or updating anything.\n\n"
	"STYLE: before each tool call, write one short sentence on what you're doing and why. When "
	"a value is unreadable or a document is ambiguous, say so plainly and ask rather than "
	"guessing. When the task is done, reply in plain text."
)

OCR_AGENT_TOOL_SLUGS = ("find_doctypes", "describe", "ocr_extract", "create", "update", "run_action")


def sync_ocr_agent(model: str | None = None) -> None:
	"""Ensure the system OCR Agent exists and is up-to-date. Called from after_migrate and
	FlowModel.after_insert, mirroring flow.assistant.assistant.sync_builtin_assistant."""
	from flow.tools.builtins import sync_builtin_tools
	from flow.tools.ocr import sync_ocr_tool

	sync_builtin_tools()
	sync_ocr_tool()

	model_name = model or frappe.db.get_value("Flow Model", {"enabled": 1}, "name")
	if not model_name:
		return

	if not frappe.db.exists("Flow Agent", OCR_AGENT_TITLE):
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": OCR_AGENT_TITLE,
				"model": model_name,
				"instructions": OCR_AGENT_INSTRUCTIONS,
				"max_iterations": OCR_AGENT_MAX_ITERATIONS,
				"tools": [{"tool": slug} for slug in OCR_AGENT_TOOL_SLUGS],
				"enabled": 1,
				"is_system_generated": 1,
			}
		).insert(ignore_permissions=True)
		return

	doc = frappe.get_doc("Flow Agent", OCR_AGENT_TITLE)
	if not doc.is_system_generated:
		return

	doc.instructions = OCR_AGENT_INSTRUCTIONS
	existing = {row.tool for row in doc.tools}
	for slug in OCR_AGENT_TOOL_SLUGS:
		if slug not in existing:
			doc.append("tools", {"tool": slug})
	doc.save(ignore_permissions=True)
