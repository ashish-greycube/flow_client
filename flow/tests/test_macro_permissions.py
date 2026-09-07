# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from flow.macros.permissions import macro_query_conditions


class TestMacroPermissions(IntegrationTestCase):
	def setUp(self):
		email = f"flow-macro-manager-{frappe.generate_hash(length=8)}@example.com"
		self.manager = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Flow Macro Manager",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		frappe.clear_cache(user=self.manager.name)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_system_manager_can_read_and_write_another_users_macro(self):
		macro = frappe.get_doc(
			{
				"doctype": "Flow Macro",
				"name": "another-users-macro",
				"owner": "macro-owner@example.com",
			}
		)

		self.assertEqual(macro_query_conditions(self.manager.name), "")
		self.assertTrue(
			frappe.has_permission("Flow Macro", "read", doc=macro, user=self.manager.name)
		)
		self.assertTrue(
			frappe.has_permission("Flow Macro", "write", doc=macro, user=self.manager.name)
		)

	def test_system_manager_can_read_another_users_macro_run(self):
		run = frappe.get_doc(
			{
				"doctype": "Flow Macro Run",
				"name": "another-users-macro-run",
				"owner": "macro-owner@example.com",
			}
		)

		self.assertTrue(
			frappe.has_permission("Flow Macro Run", "read", doc=run, user=self.manager.name)
		)
