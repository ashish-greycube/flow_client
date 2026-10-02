# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.api import resume_run, start_run, stop_run
from flow.flow.doctype.flow_run.flow_run import EMPTY_REPLY_NOTE
from flow.flow.doctype.flow_session.flow_session import NOT_RUN_TOOL_RESULT
from flow.lib.model import ChatResponse, Model
from flow.tests.test_ai_api import _agent_doc, _confirm_call, _final, _model_doc
from flow.tools.builtins import sync_builtin_tools


def _unanswered(messages: list[dict]) -> list[str]:
	"""Tool call ids in a model-bound history that have no tool result."""
	answered = {m.get("tool_call_id") for m in messages if m["role"] == "tool"}
	return [c["id"] for m in messages if m["role"] == "assistant" for c in m.get("tool_calls") or [] if c["id"] not in answered]


class TestStoppedApproval(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc()).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name, tools=[{"tool": "execute"}])).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _pause(self) -> dict:
		with patch.object(Model, "chat", return_value=_confirm_call("c1")):
			payload = start_run("do it", agent=self.agent.name)
		self.assertEqual(payload["status"], "Paused")
		return payload

	def test_next_message_after_stopping_an_approval_sends_a_valid_history(self):
		paused = self._pause()
		stop_run(paused["name"])
		sent: list[list[dict]] = []

		def chat(self, messages, tools=None, *, stream=False):
			sent.append(json.loads(json.dumps(messages)))
			return _final("ok")

		with patch.object(Model, "chat", new=chat):
			payload = start_run("try something else", session=paused["session"])

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(_unanswered(sent[0]), [])
		# The answer sits right after the call, before the new user message.
		roles = [m["role"] for m in sent[0]]
		self.assertEqual(roles[-3:], ["assistant", "tool", "user"])
		self.assertEqual(json.loads(sent[0][-2]["content"]), NOT_RUN_TOOL_RESULT)

		# Saved, so the chat stays repaired and reloads show the call as not run.
		session = frappe.get_doc("Flow Session", payload["agent_session"])
		tool_rows = [r for r in session.messages if r.role == "tool"]
		self.assertEqual([r.tool_call_id for r in tool_rows], ["c1"])
		self.assertEqual([r.idx for r in session.messages], list(range(1, len(session.messages) + 1)))

	def test_a_run_waiting_for_approval_keeps_its_call_open_and_resumes(self):
		paused = self._pause()

		with patch.object(Model, "chat", return_value=_final("done")):
			payload = resume_run(paused["name"], {"c1": "Approve"})

		self.assertEqual(payload["status"], "Completed")
		session = frappe.get_doc("Flow Session", paused["session"])
		results = [json.loads(r.content) for r in session.messages if r.role == "tool"]
		self.assertEqual(len(results), 1)
		self.assertNotEqual(results[0], NOT_RUN_TOOL_RESULT)

	def test_an_empty_model_reply_is_saved_as_a_note(self):
		empty = ChatResponse(content=None, finish_reason="stop", usage={})
		with patch.object(Model, "chat", return_value=empty):
			payload = start_run("hello", agent=self.agent.name)

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], EMPTY_REPLY_NOTE)
		session = frappe.get_doc("Flow Session", payload["session"])
		self.assertEqual(session.messages[-1].content, EMPTY_REPLY_NOTE)

	def test_deny_is_not_reported_as_an_empty_reply(self):
		paused = self._pause()

		payload = resume_run(paused["name"], {"c1": "Deny"})

		self.assertEqual(payload["status"], "Completed")
		self.assertNotEqual(payload.get("output"), EMPTY_REPLY_NOTE)
