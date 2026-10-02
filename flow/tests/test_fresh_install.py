# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow.fac_tools.registry import FAC_TOOLS
from flow.install import after_install
from flow.tests.test_ai_api import _model_doc


class TestFreshInstall(IntegrationTestCase):
	"""A newly installed site has no Flow Tools until something creates them."""

	def setUp(self):
		# Flow Tool rows can't be deleted through the ORM (system-generated guard).
		frappe.db.delete("Flow Agent Tool")
		frappe.db.delete("Flow Tool")

	def tearDown(self):
		frappe.db.rollback()

	def test_first_model_saves_and_creates_tools_and_agents(self):
		model = frappe.get_doc(_model_doc(title="Fresh Install Model")).insert()

		tools = set(frappe.get_all("Flow Tool", pluck="name"))
		self.assertTrue({tool.name for tool in FAC_TOOLS} <= tools)
		self.assertTrue({"read", "create", "describe"} <= tools)
		self.assertTrue(frappe.db.exists("Flow Agent", "Flow"))
		self.assertTrue(frappe.db.get_value("Flow Agent", "AR & Collections Operator", "model"))
		self.assertEqual(frappe.db.get_value("Flow Agent", "Flow", "model"), model.name)

	def test_install_creates_the_tools(self):
		after_install()

		tools = set(frappe.get_all("Flow Tool", pluck="name"))
		self.assertTrue({tool.name for tool in FAC_TOOLS} <= tools)
		self.assertTrue({"read", "ocr_extract", "get_file2erp_data"} <= tools)
