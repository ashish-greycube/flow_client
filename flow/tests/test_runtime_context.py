# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests import UnitTestCase

from flow.agent_instructions import RUNTIME_REQUEST_RESOLUTION_INSTRUCTIONS
from flow.flow.doctype.flow_session.flow_session import FlowSession
from flow.tools.builtins import _with_create_defaults, _with_default_transaction_dates, create, describe


class TestRuntimeContext(UnitTestCase):
	def test_prompt_uses_fresh_site_date_without_changing_stored_messages(self):
		system_row = SimpleNamespace(role="system", content="Base instructions", tool_calls=None)
		user_row = SimpleNamespace(
			role="user",
			content="What is today's date?",
			tool_calls=None,
			run=None,
		)
		session = SimpleNamespace(
			messages=[system_row, user_row],
			attachments=[],
			agent=None,
			_group_attachments_by_run=lambda: {},
			_latest_user_run=lambda: None,
			_latest_user_content=lambda: user_row.content,
			_file_injection_budget=lambda: 1000,
		)

		with (
			patch("frappe.utils.now_datetime", return_value=datetime(2026, 9, 9, 11, 30, 45)),
			patch("frappe.utils.get_system_timezone", return_value="Asia/Kolkata"),
			patch("flow.memory.memory.build_memory_block", return_value=None),
		):
			messages = FlowSession._build_prompt_messages(session)

		system_content = messages[0]["content"]
		self.assertIn("Current site date: 2026-09-09 (Wednesday)", system_content)
		self.assertIn("Current site time: 11:30:45", system_content)
		self.assertIn("Site timezone: Asia/Kolkata", system_content)
		self.assertIn("relative dates such as today, tomorrow, and yesterday", system_content)
		self.assertIn(RUNTIME_REQUEST_RESOLUTION_INSTRUCTIONS, system_content)
		self.assertIn("Do not ask solely for posting_date or transaction_date", system_content)
		self.assertIn("use your available describe, read, and search tools", system_content)
		self.assertIn("tool call itself opens Flow's approval window", system_content)

		with (
			patch("frappe.utils.now_datetime", return_value=datetime(2026, 9, 10, 0, 0, 1)),
			patch("frappe.utils.get_system_timezone", return_value="Asia/Kolkata"),
			patch("flow.memory.memory.build_memory_block", return_value=None),
		):
			refreshed_content = FlowSession._build_prompt_messages(session)[0]["content"]

		self.assertIn("Current site date: 2026-09-10 (Thursday)", refreshed_content)
		self.assertNotIn("Current site date: 2026-09-09", refreshed_content)
		self.assertEqual(system_row.content, "Base instructions")


class TestTransactionDateDefaults(UnitTestCase):
	def test_defaults_supported_date_fields_without_overwriting_user_values(self):
		for fieldname in ("posting_date", "transaction_date"):
			meta = SimpleNamespace(has_field=lambda candidate, fieldname=fieldname: candidate == fieldname)
			with patch("frappe.get_meta", return_value=meta):
				values = _with_default_transaction_dates("Test Transaction", {}, "2026-09-09")
				explicit = _with_default_transaction_dates(
					"Test Transaction",
					{fieldname: "2026-10-01"},
					"2026-09-09",
				)

			self.assertEqual(values[fieldname], "2026-09-09")
			self.assertEqual(explicit[fieldname], "2026-10-01")

	def test_confirmation_shows_the_defaulted_date(self):
		meta = SimpleNamespace(has_field=lambda fieldname: fieldname == "posting_date")
		with (
			patch("frappe.get_meta", return_value=meta),
			patch("frappe.utils.today", return_value="2026-09-09"),
		):
			prompt = create.confirm_prompt({"doctype": "Sales Invoice", "records": [{"customer": "C-1"}]})

		self.assertIn('"posting_date": "2026-09-09"', prompt)


class TestCreateDefaults(UnitTestCase):
	def test_uses_recent_company_naming_series_and_preserves_explicit_series(self):
		meta = SimpleNamespace(
			has_field=lambda fieldname: fieldname in {"company", "naming_series", "posting_date"},
			get_field=lambda _fieldname: SimpleNamespace(options="ESI.YY.#####\nSINV-.YY.-"),
		)
		with (
			patch("frappe.get_meta", return_value=meta),
			patch("frappe.get_list", return_value=[{"naming_series": "ESI.YY.#####"}]) as get_list,
		):
			resolved = _with_create_defaults(
				"Sales Invoice",
				{"company": "Unified Electro Tech Pvt Ltd"},
				"2026-09-09",
			)

		self.assertEqual(resolved["posting_date"], "2026-09-09")
		self.assertEqual(resolved["naming_series"], "ESI.YY.#####")
		self.assertEqual(get_list.call_args.kwargs["filters"]["company"], "Unified Electro Tech Pvt Ltd")

		with (
			patch("frappe.get_meta", return_value=meta),
			patch("frappe.get_list") as get_list,
		):
			explicit = _with_create_defaults(
				"Sales Invoice",
				{"company": "Unified Electro Tech Pvt Ltd", "naming_series": "SINV-.YY.-"},
				"2026-09-09",
			)

		self.assertEqual(explicit["naming_series"], "SINV-.YY.-")
		get_list.assert_not_called()

	def test_describe_exposes_effective_field_default(self):
		field = SimpleNamespace(
			fieldname="naming_series",
			label="Series",
			fieldtype="Select",
			options="ESI.YY.#####",
			default="ESI.YY.#####",
			reqd=1,
		)
		meta = SimpleNamespace(fields=[field])
		with (
			patch("frappe.has_permission", return_value=True),
			patch("frappe.get_meta", return_value=meta),
		):
			result = describe(doctype="Sales Invoice")

		self.assertEqual(result["fields"][0]["default"], "ESI.YY.#####")
