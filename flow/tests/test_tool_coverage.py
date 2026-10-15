# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

from flow.fac_tools.analysis import analyze_business_data
from flow.tools.builtins import describe, parent_doctypes, read, read_records
from flow.utils.safe_exec import _flow_builtins


class TestRead(IntegrationTestCase):
	def test_child_table_returns_requested_fields_through_its_parent(self):
		user = frappe.get_doc("User", "Administrator")
		rows = read(
			doctype="Has Role",
			filters={"parent": "Administrator"},
			fields=["parent", "role"],
			limit=200,
			parent_doctype="User",
		)
		self.assertEqual(sorted(r["role"] for r in rows), sorted(r.role for r in user.roles))

	def test_child_table_of_several_parents_asks_for_one(self):
		self.assertGreater(len(parent_doctypes("Has Role")), 1)
		with self.assertRaisesRegex(frappe.ValidationError, "pass parent_doctype"):
			read(doctype="Has Role", filters={"parent": "Administrator"}, fields=["role"])

	def test_single_parent_child_table_is_found_automatically(self):
		if not frappe.db.exists("DocType", "Payment Entry Reference"):
			self.skipTest("ERPNext is not installed")
		self.assertEqual(parent_doctypes("Payment Entry Reference"), ["Payment Entry"])
		row = frappe.db.get_value("Payment Entry Reference", {"parenttype": "Payment Entry"}, ["parent", "reference_name"], as_dict=True)
		if not row:
			self.skipTest("No payment references on this site")
		rows = read(
			doctype="Payment Entry Reference",
			filters={"parent": row.parent},
			fields=["parent", "reference_name"],
			limit=200,
		)
		self.assertIn({"parent": row.parent, "reference_name": row.reference_name}, rows)

	def test_partial_read_says_so(self):
		result = read(doctype="DocType", fields=["name"], limit=1)
		self.assertTrue(result["has_more"])
		self.assertEqual(len(result["rows"]), 1)
		self.assertIn("PARTIAL", result["note"])

	def test_complete_read_is_a_plain_list(self):
		result = read(doctype="User", filters={"name": "Administrator"}, fields=["name"])
		self.assertEqual(result, [{"name": "Administrator"}])

	def test_scripts_always_get_a_list(self):
		self.assertIs(_flow_builtins()["read"], read_records)
		self.assertEqual(len(read_records(doctype="DocType", fields=["name"], limit=1)), 1)


class TestDescribe(IntegrationTestCase):
	def test_leaves_out_empty_attributes_and_shortens_long_option_lists(self):
		fields = describe(doctype="DocField")["fields"]
		self.assertTrue(all(value not in (None, "", False) for f in fields for value in f.values()))
		fieldtype = next(f for f in fields if f["fieldname"] == "fieldtype")
		self.assertLessEqual(len(fieldtype["options"]), 13)
		self.assertTrue(fieldtype["options"][-1].startswith("… +"))

	def test_fields_filter_returns_only_those_and_names_unknown_ones(self):
		result = describe(doctype="User", fields=["email", "first_name", "no_such_field"])
		self.assertEqual([f["fieldname"] for f in result["fields"]], ["email", "first_name"])
		self.assertEqual(result["unknown_fields"], ["no_such_field"])

	def test_child_table_lists_its_parents(self):
		result = describe(doctype="Has Role", fields=["role"])
		self.assertIn("User", result["parent_doctypes"])
		self.assertTrue(result["permissions"]["read"])


class TestServerSideAnalysis(IntegrationTestCase):
	def setUp(self):
		self.tag = frappe.generate_hash(length=8)
		for priority, date in (("High", "2026-10-01"), ("High", "2026-10-03"), ("High", "2026-12-01"), ("Low", "2026-10-02")):
			frappe.get_doc(
				{"doctype": "ToDo", "description": f"Pay vendor {self.tag}", "priority": priority, "date": date}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def analyze(self, **kwargs):
		return analyze_business_data(doctype="ToDo", filters={"description": ["like", f"%{self.tag}%"]}, **kwargs)

	def test_aggregate_totals_per_group(self):
		result = self.analyze(analysis_type="aggregate", group_by=["priority"], aggregates=["count", "max:date"])
		by_priority = {row["priority"]: row for row in result["rows"]}
		self.assertEqual((by_priority["High"]["count"], by_priority["Low"]["count"]), (3, 1))
		self.assertEqual(str(by_priority["High"]["max_date"]), "2026-12-01")
		self.assertEqual(result["rows"][0]["priority"], "High")

	def test_aggregate_rejects_unknown_fields_and_functions(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown fields"):
			self.analyze(analysis_type="aggregate", group_by=["no_such_field"])
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown aggregate"):
			self.analyze(analysis_type="aggregate", group_by=["priority"], aggregates=["median:date"])

	def test_duplicates_match_ignoring_case_and_spacing_within_days(self):
		frappe.get_doc(
			{"doctype": "ToDo", "description": f"PAY  vendor {self.tag}_x000D_", "priority": "Medium", "date": "2026-10-02"}
		).insert(ignore_permissions=True)
		result = self.analyze(analysis_type="duplicates", fields=["description"], date_field="date", within_days=7)
		self.assertEqual(result["records_scanned"], 5)
		self.assertEqual(result["duplicate_groups"], 1)
		self.assertEqual(result["groups"][0]["count"], 4)
		self.assertEqual([str(d) for d in result["groups"][0]["dates"]], ["2026-10-01", "2026-10-02", "2026-10-02", "2026-10-03"])

	def test_duplicates_without_a_date_window_group_everything_that_matches(self):
		result = self.analyze(analysis_type="duplicates", fields=["description", "priority"])
		self.assertEqual([g["count"] for g in result["groups"]], [3])

	def test_field_changes_lists_edits_of_the_chosen_fields_from_the_change_history(self):
		# The history Frappe records on save (track_changes), written directly so the test does
		# not depend on the runner recording it.
		todo = frappe.get_last_doc("ToDo", filters={"description": ["like", f"%{self.tag}%"]})
		frappe.get_doc(
			{
				"doctype": "Version",
				"ref_doctype": "ToDo",
				"docname": todo.name,
				"data": json.dumps({"changed": [["priority", "High", "Low"], ["status", "Open", "Closed"]]}),
			}
		).insert(ignore_permissions=True)
		result = analyze_business_data(doctype="ToDo", analysis_type="field_changes", fields=["priority"], since="2000-01-01")
		mine = [c for c in result["changes"] if c["docname"] == todo.name]
		self.assertEqual([(c["field"], c["old"], c["new"]) for c in mine], [("priority", "High", "Low")])
		self.assertEqual(mine[0]["changed_by"], "Administrator")
