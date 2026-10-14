# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from flow.flow.doctype.flow_run.flow_run import create_run
from flow.lib.agent import Agent, Question, RunResult
from flow.lib.background import _mark_failed_if_running
from flow.lib.model import ChatResponse, Model
from flow.routing.conversation import _run_details


def _final(text: str = "done") -> ChatResponse:
	return ChatResponse(
		content=text, finish_reason="stop", usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
	)


class TestRunDuration(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def session(self):
		return Agent(model=Model(model_id="openai/gpt-4o-mini"), name="Timer", instructions="be terse").new_session()

	def run_started(self, seconds_ago: float):
		return create_run(
			source="Manual",
			input="x",
			session=self.session().name,
			started_at=now_datetime() - timedelta(seconds=seconds_ago),
		)

	def assertAbout(self, ms, expected_ms):
		self.assertIsNotNone(ms)
		self.assertGreaterEqual(ms, expected_ms)
		self.assertLess(ms, expected_ms + 3000)

	def test_chat_records_duration_from_the_send_time(self):
		with patch.object(Model, "chat", return_value=_final("hi")):
			run = self.session().chat("hello", started_at=now_datetime() - timedelta(seconds=5))
		self.assertEqual(run.status, "Completed")
		self.assertAbout(run.duration_ms, 5000)
		self.assertIsNone(run.active_since)

	def test_run_without_send_time_counts_from_creation(self):
		with patch.object(Model, "chat", return_value=_final("hi")):
			run = self.session().chat("hello")
		self.assertAbout(run.duration_ms, 0)

	def test_approval_wait_is_not_counted(self):
		run = self.run_started(4)
		run.apply_result(RunResult(output=None, messages=[], paused=True, questions=[Question(prompt="OK?")]))
		self.assertEqual(run.status, "Paused")
		self.assertAbout(run.duration_ms, 4000)
		self.assertIsNone(run.active_since)

		# The user takes an hour to answer; then the resumed stretch works for 2 seconds.
		run.start_clock()
		run.reload()
		run.db_set("active_since", now_datetime() - timedelta(seconds=2), update_modified=False)
		run.apply_result(RunResult(output="done", messages=[], iterations=1))
		self.assertEqual(run.status, "Completed")
		self.assertAbout(run.duration_ms, 6000)

	def test_failed_run_records_its_duration(self):
		run = self.run_started(3)
		run.mark_failed("boom")
		self.assertAbout(run.duration_ms, 3000)
		self.assertIsNone(run.active_since)

	def test_background_failure_records_its_duration(self):
		run = self.run_started(3)
		_mark_failed_if_running(run.name, "worker died")
		row = frappe.db.get_value("Flow Run", run.name, ["status", "duration_ms", "active_since"], as_dict=True)
		self.assertEqual(row.status, "Failed")
		self.assertAbout(row.duration_ms, 3000)
		self.assertIsNone(row.active_since)

	def test_chat_payload_carries_durations_and_errors(self):
		done = self.run_started(2)
		done.apply_result(RunResult(output="done", messages=[], iterations=1))
		failed = self.run_started(1)
		failed.mark_failed("boom")
		running = self.run_started(1)

		details = _run_details({done.name, failed.name, running.name})
		self.assertAbout(details["run_durations"][done.name], 2000)
		self.assertAbout(details["run_durations"][failed.name], 1000)
		self.assertNotIn(running.name, details["run_durations"])
		self.assertEqual(details["run_errors"], {failed.name: "boom"})

	def test_active_run_reports_time_worked_so_far(self):
		from flow.api.api import get_active_run

		run = self.run_started(7)
		with (
			patch("flow.routing.conversation.resolve_chat", return_value=(None, frappe._dict(name=run.session))),
			patch("flow.lib.background.active_stream", return_value="stream-1"),
		):
			active = get_active_run(run.session)
		self.assertEqual((active["run"], active["stream"]), (run.name, "stream-1"))
		self.assertAbout(active["elapsed_ms"], 7000)
