# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import unittest
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.api import resume_run, start_run
from flow.lib.model import ChatResponse, Model, ToolCall
from flow.routing.selector import RoutingDecision
from flow.tools.builtins import sync_builtin_tools


def _final(text: str = "done") -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


@unittest.skip("Skills rollout is deferred.")
class TestFlowSkills(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Skill Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Skill Test Agent",
				"model": self.model.name,
				"instructions": "Base instructions.",
				"enabled": 1,
				"tools": [{"tool": "describe"}, {"tool": "read"}, {"tool": "create"}],
			}
		).insert()
		self.skill = frappe.get_doc(
			{
				"doctype": "Flow Skill",
				"title": "Create Test Record",
				"command": "create-test-record",
				"description": "Create one test record.",
				"instructions": "Create only the requested test record.",
				"tools": [{"tool": "describe"}, {"tool": "create"}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_slash_command_injects_instructions_and_narrows_tools(self):
		captured: dict[str, Any] = {}

		def chat(_model, messages, tools=None, **_kwargs):
			captured["messages"] = messages
			captured["tools"] = tools
			return _final()

		with patch.object(Model, "chat", new=chat):
			payload = start_run(
				"/create-test-record create it", agent=self.agent.name, routing="manual"
			)

		run = frappe.get_doc("Flow Run", payload["name"])
		snapshot = json.loads(run.config_snapshot)
		self.assertEqual(payload["agent"], self.agent.name)
		self.assertEqual(payload["skill"], self.skill.name)
		self.assertEqual(run.skill, self.skill.name)
		self.assertEqual(snapshot["skill"]["command"], self.skill.command)
		self.assertIn("ACTIVE SKILL /create-test-record", captured["messages"][0]["content"])
		self.assertEqual({tool["function"]["name"] for tool in captured["tools"]}, {"describe", "create"})

	def test_auto_mode_uses_the_router_selected_agent(self):
		decision = RoutingDecision("Initial", self.agent.name, 0.98, "Best match for the request.")
		with (
			patch("flow.routing.orchestrator.select_agent", return_value=decision),
			patch.object(Model, "chat", return_value=_final()),
		):
			payload = start_run("/create-test-record create it", routing="auto")

		self.assertEqual(payload["agent"], self.agent.name)
		self.assertEqual(payload["skill"], self.skill.name)

	def test_selected_agent_must_provide_all_skill_tools(self):
		read_only_agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Read Only Skill Test Agent",
				"model": self.model.name,
				"instructions": "Read only.",
				"enabled": 1,
				"tools": [{"tool": "describe"}],
			}
		).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "unavailable on this agent: create"):
			start_run(
				"/create-test-record create it", agent=read_only_agent.name, routing="manual"
			)

	def test_unknown_slash_command_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown skill command"):
			start_run("/not-a-real-skill do something")

	def test_resume_uses_the_persisted_skill_snapshot(self):
		tool_call = ChatResponse(
			content=None,
			tool_calls=[
				ToolCall(
					id="create-1",
					name="create",
					arguments={"doctype": "ToDo", "records": [{"description": "Test"}]},
				)
			],
			finish_reason="tool_calls",
			usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
		)
		with patch.object(Model, "chat", return_value=tool_call):
			payload = start_run(
				"/create-test-record create it", agent=self.agent.name, routing="manual"
			)

		self.assertEqual(payload["status"], "Paused")
		self.skill.set("tools", [])
		self.skill.save()
		resumed = resume_run(payload["name"], {"create-1": "Deny"})
		self.assertEqual(resumed["status"], "Completed")
