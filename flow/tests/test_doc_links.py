# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

from frappe.tests import UnitTestCase

from flow.lib.doc_links import collect_document_references, linkify_document_mentions


def _assistant_call(call_id: str, tool: str, arguments: dict) -> dict:
	return {
		"role": "assistant",
		"content": None,
		"tool_calls": [
			{"id": call_id, "type": "function", "function": {"name": tool, "arguments": json.dumps(arguments)}}
		],
	}


def _tool_result(call_id: str, result) -> dict:
	return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)}


class TestCollectDocumentReferences(UnitTestCase):
	def test_create_result_maps_created_names_to_doctype(self):
		messages = [
			_assistant_call("c1", "create", {"doctype": "ToDo", "records": [{"description": "x"}]}),
			_tool_result("c1", {"doctype": "ToDo", "created": ["TODO-001", "TODO-002"]}),
		]
		self.assertEqual(
			collect_document_references(messages), {"TODO-001": "ToDo", "TODO-002": "ToDo"}
		)

	def test_read_result_maps_row_names_to_doctype(self):
		messages = [
			_assistant_call("c1", "read", {"doctype": "Customer", "filters": {}}),
			_tool_result("c1", [{"name": "CUST-001"}, {"name": "CUST-002"}]),
		]
		self.assertEqual(
			collect_document_references(messages), {"CUST-001": "Customer", "CUST-002": "Customer"}
		)

	def test_describe_and_run_action_results_are_collected(self):
		messages = [
			_assistant_call("c1", "describe", {"doctype": "Sales Order", "name": "SO-0001"}),
			_tool_result("c1", {"doctype": "Sales Order", "name": "SO-0001", "fields": []}),
			_assistant_call("c2", "run_action", {"doctype": "Sales Order", "names": ["SO-0001"], "action": "submit"}),
			_tool_result("c2", {"action": "submit", "results": [{"name": "SO-0001", "result": {}}]}),
		]
		self.assertEqual(collect_document_references(messages), {"SO-0001": "Sales Order"})

	def test_ignores_unrelated_tools_and_missing_doctype(self):
		messages = [
			_assistant_call("c1", "execute", {"code": "result = 1"}),
			_tool_result("c1", 1),
			_assistant_call("c2", "find_doctypes", {"search": "Sales"}),
			_tool_result("c2", [{"name": "Sales Order", "module": "Selling"}]),
		]
		self.assertEqual(collect_document_references(messages), {})


class TestLinkifyDocumentMentions(UnitTestCase):
	def test_wraps_bare_mention_with_form_link(self):
		text = linkify_document_mentions("I created SO-0001 for you.", {"SO-0001": "Sales Order"})
		self.assertEqual(text, "I created [SO-0001](/desk/sales-order/SO-0001) for you.")

	def test_wraps_every_mention(self):
		text = linkify_document_mentions(
			"SO-0001 is ready. See SO-0001 for details.", {"SO-0001": "Sales Order"}
		)
		self.assertEqual(text.count("[SO-0001](/desk/sales-order/SO-0001)"), 2)

	def test_does_not_double_link_existing_markdown_links(self):
		original = "Already linked: [SO-0001](/desk/sales-order/SO-0001)."
		self.assertEqual(linkify_document_mentions(original, {"SO-0001": "Sales Order"}), original)

	def test_does_not_link_inside_code_spans(self):
		original = "The record id is `SO-0001` in the database."
		self.assertEqual(linkify_document_mentions(original, {"SO-0001": "Sales Order"}), original)

	def test_does_not_partial_match_longer_names(self):
		text = linkify_document_mentions(
			"SO-00010 is unrelated to SO-0001.", {"SO-0001": "Sales Order"}
		)
		self.assertEqual(text, "SO-00010 is unrelated to [SO-0001](/desk/sales-order/SO-0001).")

	def test_no_references_returns_text_unchanged(self):
		self.assertEqual(linkify_document_mentions("no mentions here", {}), "no mentions here")

	def test_none_text_passthrough(self):
		self.assertIsNone(linkify_document_mentions(None, {"SO-0001": "Sales Order"}))
