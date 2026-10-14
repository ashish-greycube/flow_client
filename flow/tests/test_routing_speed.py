# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.assistant import ASSISTANT_AGENT_TITLE
from flow.lib.model import ChatResponse
from flow.routing import selector
from flow.routing.selector import select_agent

AR_SPECIALIST = {
	"name": "AR & Collections Operator",
	"title": "AR & Collections Operator",
	"model": "Router Model",
	"routing_domain": "Accounts Receivable",
	"routing_description": "Sales invoices, receivables and collections follow-up",
	"routing_doctypes": json.dumps(["Sales Invoice", "Customer", "Payment Entry"]),
	"routing_priority": 0,
}
ATTENDANCE_AUDITOR = {
	"name": "Attendance & Leave Integrity Auditor",
	"title": "Attendance & Leave Integrity Auditor",
	"model": "Router Model",
	"routing_domain": "Attendance",
	"routing_description": "Attendance and leave integrity checks",
	"routing_doctypes": json.dumps(["Attendance", "Leave Application"]),
	"routing_priority": 0,
}


class TestReportRequestsGoToFlow(IntegrationTestCase):
	def route(self, text: str, current_agent: str | None = None):
		with (
			patch.object(selector, "_routing_candidates", return_value=[AR_SPECIALIST, ATTENDANCE_AUDITOR]),
			patch.object(selector, "Model") as model_class,
		):
			model_class.return_value.chat.return_value = ChatResponse(
				content='{"agent": null, "confidence": 0.1, "reason": "none"}'
			)
			return select_agent(text, current_agent=current_agent), model_class

	def test_report_and_figure_requests_route_to_flow_without_the_classifier(self):
		for text in (
			"Give me the PL statement from 01 April 2025 to today",
			'For company named "J P Jewellers", give me total sales for today',
			"For Company J P Jewellers, rate stores (cost center) based on the sales",
			"Show the balance sheet as on 31 March 2026",
			"Month-wise sales vs purchases for this year with a bar chart",
			"Top 10 customers by invoice value",
			"How much did we collect from customers in September?",
		):
			with self.subTest(text=text):
				decision, model_class = self.route(text)
				self.assertEqual((decision.agent, decision.confidence), (ASSISTANT_AGENT_TITLE, 1.0))
				self.assertEqual(decision.action, "Initial")
				model_class.assert_not_called()

	def test_report_request_switches_a_specialist_conversation_to_flow(self):
		decision, _ = self.route("Now give me the trial balance", current_agent="AR & Collections Operator")
		self.assertEqual((decision.agent, decision.action), (ASSISTANT_AGENT_TITLE, "Switch"))

	def test_actions_audits_and_named_agents_still_go_through_routing(self):
		for text in (
			"If sales invoice SINV-26-00154 has grand total value more than 100000 then send email to accounts",
			"Audit attendance for yesterday and give me a summary",
			"Ask the Ledger Scrutiny Auditor for a summary of last month",
		):
			with self.subTest(text=text):
				decision, _ = self.route(text)
				self.assertFalse(decision.reason.startswith("Reports, statements"))

	def test_specialist_requests_without_figures_still_reach_the_specialist(self):
		decision, _ = self.route("Show overdue Sales Invoice records for collections follow-up")
		self.assertEqual(decision.agent, "AR & Collections Operator")


class TestRoutingModelAndTimeout(IntegrationTestCase):
	def setUp(self):
		self.fast = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Routing Speed Test", "model_id": "openai/gpt-4.1-nano", "enabled": 1}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype="Flow Settings")

	def set_routing_model(self, value):
		frappe.db.set_single_value("Flow Settings", "routing_model", value)
		frappe.clear_cache(doctype="Flow Settings")

	def test_routing_model_from_settings_wins_over_the_agent_model(self):
		self.set_routing_model(self.fast.name)
		self.assertEqual(selector._routing_model(None, None, [AR_SPECIALIST]), self.fast.name)

	def test_unset_or_disabled_routing_model_falls_back_to_the_agent_model(self):
		agent_model = frappe.db.get_value("Flow Agent", ASSISTANT_AGENT_TITLE, "model")
		if not agent_model:
			self.skipTest("The Flow agent has no model on this site")
		self.set_routing_model(None)
		self.assertEqual(selector._routing_model(None, None, [AR_SPECIALIST]), agent_model)
		self.set_routing_model(self.fast.name)
		self.fast.db_set("enabled", 0)
		self.assertEqual(selector._routing_model(None, None, [AR_SPECIALIST]), agent_model)

	def test_slow_classifier_falls_back_to_flow_within_the_timeout(self):
		def slow(*args, **kwargs):
			time.sleep(2)
			return ChatResponse(content='{"agent": "AR & Collections Operator", "confidence": 0.99}')

		with (
			patch.object(selector, "ROUTING_TIMEOUT", 0.3),
			patch.object(selector, "_routing_candidates", return_value=[AR_SPECIALIST]),
			patch.object(selector, "_routing_model", return_value=self.fast.name),
			patch.object(selector.Model, "chat", side_effect=slow),
		):
			started = time.monotonic()
			decision = select_agent("Please look into this")
			elapsed = time.monotonic() - started
		self.assertLess(elapsed, 1.5)
		self.assertEqual((decision.agent, decision.action), (ASSISTANT_AGENT_TITLE, "Fallback"))

	def test_classifier_runs_with_the_routing_timeout(self):
		with patch.object(selector, "Model") as model_class:
			model_class.return_value.chat.return_value = ChatResponse(content="{}")
			selector._classify(self.fast.name, [{"role": "user", "content": "x"}])
		model_class.assert_called_once_with(self.fast.name, timeout=selector.ROUTING_TIMEOUT)
