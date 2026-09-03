# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from flow.fac_tools.analysis import _validate_select
from flow.fac_tools.exports import MAX_EXPORT_LIMIT, _safe_filename, _validate_fields
from flow.fac_tools.report_filters import discover_filters
from flow.fac_tools.registry import FAC_TOOLS, sync_fac_tools


class TestFACToolDefinitions(UnitTestCase):
	def test_names_are_unique(self):
		names = [advanced_tool.name for advanced_tool in FAC_TOOLS]
		self.assertEqual(len(names), len(set(names)))
		self.assertEqual(len(names), 16)

	def test_all_tools_have_closed_object_schemas(self):
		for advanced_tool in FAC_TOOLS:
			self.assertEqual(advanced_tool.parameters["type"], "object")
			self.assertFalse(advanced_tool.parameters["additionalProperties"])

	def test_sql_validator_allows_select_and_cte(self):
		self.assertEqual(_validate_select("SELECT name FROM `tabUser`;"), "SELECT name FROM `tabUser`")
		self.assertEqual(_validate_select("WITH users AS (SELECT name FROM `tabUser`) SELECT * FROM users"), "WITH users AS (SELECT name FROM `tabUser`) SELECT * FROM users")

	def test_sql_validator_rejects_writes_and_multiple_statements(self):
		for query in (
			"UPDATE `tabUser` SET enabled = 0",
			"SELECT name FROM `tabUser`; SELECT name FROM `tabRole`",
			"WITH changed AS (DELETE FROM `tabUser` RETURNING name) SELECT * FROM changed",
		):
			with self.assertRaises(frappe.PermissionError):
				_validate_select(query)

	def test_report_filter_discovery_handles_dynamic_defaults_and_select_values(self):
		script = '''
		frappe.query_reports["Example"] = {filters: [
			{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1},
			{fieldname: "from_date", fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)},
			{fieldname: "group_by", fieldtype: "Select", options: ["", {label: __("Customer"), value: "Customer"}], default: "Customer"},
		]};
		'''
		with patch("frappe.desk.query_report.get_script", return_value={"script": script}):
			filters, diagnostics = discover_filters("Example")
		self.assertFalse(diagnostics)
		self.assertEqual([row["fieldname"] for row in filters], ["company", "from_date", "group_by"])
		self.assertEqual(filters[2]["options"], ["Customer"])
		self.assertNotEqual(filters[1]["default"], frappe.utils.today())

	def test_excel_export_limit_and_filename_contract(self):
		self.assertEqual(MAX_EXPORT_LIMIT, 5_000)
		self.assertEqual(_safe_filename(" Assistant Response.xlsx "), "assistant_response")

	def test_excel_export_accepts_plain_fields_only(self):
		meta = frappe.get_meta("DocType")
		_validate_fields(meta, ["name", "module"])
		with self.assertRaises(frappe.ValidationError):
			_validate_fields(meta, ["count(*) as count"])


class TestFACToolSync(IntegrationTestCase):
	def test_sync_is_idempotent_and_uses_isolated_import_paths(self):
		sync_fac_tools()
		sync_fac_tools()
		rows = frappe.get_all(
			"Flow Tool",
			filters={"name": ["in", [advanced_tool.name for advanced_tool in FAC_TOOLS]]},
			fields=["name", "import_path", "is_system_generated"],
		)
		self.assertEqual(len(rows), len(FAC_TOOLS))
		for row in rows:
			self.assertTrue(row.import_path.startswith("flow.fac_tools."))
			self.assertTrue(row.is_system_generated)
