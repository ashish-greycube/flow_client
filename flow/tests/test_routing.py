# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.api import get_chat, get_chat_history, start_run
from flow.assistant import ASSISTANT_AGENT_TITLE, sync_builtin_assistant
from flow.lib.model import ChatResponse, Model
from flow.routing.selector import RoutingDecision, select_agent
from flow.tools.builtins import sync_builtin_tools


def _final(text: str = "done") -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestAgentSelector(IntegrationTestCase):
	def test_explicit_doctype_match_uses_deterministic_route(self):
		candidates = [
			{
				"name": "Purchase Specialist",
				"title": "Purchase Specialist",
				"routing_domain": "Accounts Payable",
				"routing_doctypes": json.dumps(["Purchase Invoice"]),
				"routing_priority": 0,
			},
			{
				"name": "Support Specialist",
				"title": "Support Specialist",
				"routing_domain": "Support",
				"routing_doctypes": json.dumps(["Issue"]),
				"routing_priority": 0,
			},
		]
		with patch("flow.routing.selector._routing_candidates", return_value=candidates):
			decision = select_agent("Show overdue Purchase Invoice records")

		self.assertEqual(decision.agent, "Purchase Specialist")
		self.assertEqual(decision.action, "Initial")

	def test_sales_tracker_request_does_not_match_short_ar_domain_substring(self):
		candidates = [
			{
				"name": "AR Specialist",
				"title": "AR Specialist",
				"routing_domain": "ar",
				"routing_description": "Receivables, collections, and overdue sales invoices",
				"routing_doctypes": json.dumps(["Sales Invoice", "Customer"]),
				"routing_priority": 0,
			},
			{
				"name": "Sales Analysis Agent",
				"title": "Sales Analysis Agent",
				"routing_domain": "sales-reporting",
				"routing_description": "Filtered Excel exports from Sales Tracker Direct",
				"routing_doctypes": json.dumps(["Sales Order"]),
				"routing_examples": "Export open Sales Tracker Direct orders to Excel.",
				"routing_priority": 0,
			},
		]
		with (
			patch("flow.routing.selector._routing_candidates", return_value=candidates),
			patch("flow.routing.selector.Model") as model_class,
		):
			decision = select_agent(
				"Give sales tracker information of all open order of customer Bharat Heavy "
				"Electrical LTD in Downloadable excel format.",
				current_agent="AR Specialist",
			)

		self.assertEqual(decision.agent, "Sales Analysis Agent")
		self.assertEqual(decision.action, "Switch")
		model_class.assert_not_called()

	def test_low_confidence_classifier_falls_back_to_flow(self):
		candidates = [
			{
				"name": "Purchase Specialist",
				"title": "Purchase Specialist",
				"model": "Router Model",
				"routing_description": "Purchase invoice matching",
				"routing_priority": 0,
			}
		]
		response = _final('{"agent":"Purchase Specialist","confidence":0.4,"reason":"unclear"}')
		with (
			patch("flow.routing.selector._routing_candidates", return_value=candidates),
			patch("flow.routing.selector._routing_model", return_value="Router Model"),
			patch("flow.routing.selector.Model") as model_class,
		):
			model_class.return_value.chat.return_value = response
			decision = select_agent("Please investigate this")

		self.assertEqual(decision.agent, ASSISTANT_AGENT_TITLE)
		self.assertEqual(decision.action, "Fallback")

	def test_required_doctypes_override_out_of_scope_current_agent(self):
		candidates = [
			{
				"name": "Attendance Specialist",
				"title": "Attendance Specialist",
				"model": "Router Model",
				"routing_description": "Attendance and leave checks",
				"routing_doctypes": json.dumps(["Attendance", "Leave Application"]),
				"routing_priority": 0,
			},
			{
				"name": "Payroll Specialist",
				"title": "Payroll Specialist",
				"model": "Router Model",
				"routing_description": "Salary slip and payroll status checks",
				"routing_doctypes": json.dumps(["Salary Slip", "Payroll Entry"]),
				"routing_priority": 0,
			},
		]
		response = _final(
			json.dumps(
				{
					"agent": "Attendance Specialist",
					"confidence": 0.78,
					"required_doctypes": ["Salary Slip", "Payroll Entry"],
					"reason": "Salary status requires payroll records.",
				}
			)
		)
		with (
			patch("flow.routing.selector._routing_candidates", return_value=candidates),
			patch("flow.routing.selector._routing_model", return_value="Router Model"),
			patch("flow.routing.selector.Model") as model_class,
		):
			model_class.return_value.chat.return_value = response
			decision = select_agent(
				"What is the employee salary status for August?",
				current_agent="Attendance Specialist",
			)

		self.assertEqual(decision.agent, "Payroll Specialist")
		self.assertEqual(decision.action, "Switch")


class TestAutoRoutedConversation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Routing Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		sync_builtin_assistant(model=self.model.name)
		self.first_agent = self._agent("Routing Purchase Agent", "Purchase work")
		self.second_agent = self._agent("Routing Bank Agent", "Bank work")

	def tearDown(self):
		frappe.db.rollback()

	def _agent(self, title: str, description: str):
		return frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": title,
				"model": self.model.name,
				"instructions": f"Handle {description}.",
				"enabled": 1,
				"allow_auto_routing": 1,
				"routing_description": description,
			}
		).insert()

	def _start(self, text: str, decision: RoutingDecision, **kwargs: Any) -> dict[str, Any]:
		with (
			patch("flow.routing.orchestrator.select_agent", return_value=decision),
			patch.object(Model, "chat", return_value=_final(f"reply to {text}")),
		):
			return start_run(text, routing="auto", **kwargs)

	def test_first_auto_turn_creates_parent_conversation(self):
		result = self._start(
			"Check purchase invoices",
			RoutingDecision("Initial", self.first_agent.name, 0.92, "Purchase request"),
		)

		self.assertNotEqual(result["session"], result["agent_session"])
		session = frappe.get_doc("Flow Session", result["agent_session"])
		self.assertEqual(session.conversation, result["session"])
		self.assertEqual(session.agent, self.first_agent.name)
		self.assertEqual(result["routing_action"], "Initial")

	def test_new_domain_switches_internal_session_but_keeps_visible_chat(self):
		first = self._start(
			"Check purchase invoices",
			RoutingDecision("Initial", self.first_agent.name, 0.92, "Purchase request"),
		)
		second = self._start(
			"Now reconcile bank entries",
			RoutingDecision("Switch", self.second_agent.name, 0.9, "Bank request"),
			session=first["session"],
		)

		self.assertEqual(second["session"], first["session"])
		self.assertNotEqual(second["agent_session"], first["agent_session"])
		segment = frappe.get_doc("Flow Session", second["agent_session"])
		self.assertEqual(segment.previous_session, first["agent_session"])
		self.assertIn("Check purchase invoices", segment.handoff_summary)
		self.assertIn("reply to Check purchase invoices", segment.handoff_summary)

		chat = get_chat(first["session"])
		user_messages = [row for row in chat["messages"] if row["role"] == "user"]
		self.assertEqual(
			[row["content"] for row in user_messages],
			["Check purchase invoices", "Now reconcile bank entries"],
		)

	def test_continue_reuses_current_agent_session(self):
		first = self._start(
			"Check purchase invoices",
			RoutingDecision("Initial", self.first_agent.name, 0.92, "Purchase request"),
		)
		second = self._start(
			"Only show overdue ones",
			RoutingDecision("Continue", self.first_agent.name, 0.94, "Contextual follow-up"),
			session=first["session"],
		)

		self.assertEqual(second["agent_session"], first["agent_session"])
		self.assertEqual(second["routing_action"], "Continue")

	def test_manual_routing_keeps_explicit_agent(self):
		with patch.object(Model, "chat", return_value=_final()):
			result = start_run(
				"Use this specialist",
				agent=self.second_agent.name,
				routing="manual",
			)

		self.assertEqual(result["agent"], self.second_agent.name)
		self.assertEqual(result["routing_action"], "Manual")

	def test_history_contains_parent_not_internal_segments(self):
		result = self._start(
			"Check purchase invoices",
			RoutingDecision("Initial", self.first_agent.name, 0.92, "Purchase request"),
		)

		names = [row["name"] for row in get_chat_history()]
		self.assertIn(result["session"], names)
		self.assertNotIn(result["agent_session"], names)
