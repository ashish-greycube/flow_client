# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.fac_tools.prebuilt_agents import _sync_agent, _tool_names
from flow.fac_tools.registry import sync_fac_tools
from flow.tests.test_ai_api import _model_doc
from flow.tools.builtins import sync_builtin_tools

SPEC = {
	"title": "Test Prebuilt Sync Agent",
	"agent_slug": "test-prebuilt-sync-agent",
	"nature": "Operator",
	"status": "Published",
	"domain": "Testing",
	"description": "Checks that a resync keeps admin choices.",
	"doctypes_required": ["ToDo"],
	"writes": [{"doctype": "ToDo", "mode": "draft"}],
	"version": "1",
}


class TestPrebuiltAgentSync(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()
		with patch("flow.fac_tools.prebuilt_agents.sync_prebuilt_agents"), patch(
			"flow.fac_tools.registry._attach_to_builtin_agent"
		):
			sync_fac_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc(title="Prebuilt Sync Model")).insert()
		_sync_agent(SPEC, self.model.name)
		self.agent = frappe.get_doc("Flow Agent", SPEC["title"])

	def tearDown(self):
		frappe.db.rollback()

	def _resync(self, spec=SPEC):
		_sync_agent(spec, self.model.name)
		return frappe.get_doc("Flow Agent", SPEC["title"])

	def test_new_agent_gets_catalog_tools_and_is_enabled(self):
		self.assertTrue(self.agent.enabled)
		self.assertEqual({row.tool for row in self.agent.tools}, set(_tool_names(SPEC)))

	def test_tool_permission_overrides_survive_a_resync(self):
		for row in self.agent.tools:
			if row.tool == "create":
				row.permission = "Blocked"
			if row.tool == "read":
				row.permission = "Always Allow"
		self.agent.save()

		agent = self._resync()

		permissions = {row.tool: row.permission for row in agent.tools}
		self.assertEqual(permissions["create"], "Blocked")
		self.assertEqual(permissions["read"], "Always Allow")

	def test_a_disabled_agent_stays_disabled(self):
		self.agent.enabled = 0
		self.agent.save()

		self.assertFalse(self._resync().enabled)

	def test_auto_routing_choice_survives_a_resync(self):
		self.agent.allow_auto_routing = 0
		self.agent.save()

		self.assertFalse(self._resync().allow_auto_routing)

	def test_a_tool_the_admin_added_is_kept(self):
		self.agent.append("tools", {"tool": "find_doctypes"})
		self.agent.save()

		self.assertIn("find_doctypes", {row.tool for row in self._resync().tools})

	def test_missing_catalog_tools_are_added_back(self):
		self.agent.set("tools", [row for row in self.agent.tools if row.tool != "update"])
		self.agent.save()

		self.assertIn("update", {row.tool for row in self._resync().tools})

	def test_catalog_text_is_refreshed(self):
		self.agent.instructions = "edited by hand"
		self.agent.routing_description = "edited by hand"
		self.agent.save()

		agent = self._resync()

		self.assertIn(SPEC["description"], agent.instructions)
		self.assertEqual(agent.routing_description, SPEC["description"])

	def test_agent_is_disabled_when_the_site_cannot_run_it(self):
		missing = {**SPEC, "doctypes_required": ["ToDo", "No Such DocType For Sync"]}

		self.assertFalse(self._resync(missing).enabled)

	def test_a_coming_soon_agent_the_admin_enabled_stays_enabled(self):
		coming_soon = {**SPEC, "status": "Coming Soon"}

		self.assertTrue(self._resync(coming_soon).enabled)
