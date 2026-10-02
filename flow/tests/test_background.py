# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import time
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.wrappers import Response

from flow.api import get_active_run, get_run_events, recover_session, resume_run, start_run, stop_run
from flow.lib import background
from flow.lib.model import Model
from flow.tests.test_ai_api import _agent_doc, _confirm_call, _final, _model_doc, _stream_chat
from flow.tools.builtins import sync_builtin_tools


class TestBackgroundRun(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc()).insert()
		self.agent = frappe.get_doc(
			_agent_doc(self.model.name, tools=[{"tool": "read"}, {"tool": "execute"}])
		).insert()
		self.runs: list[str] = []

	def tearDown(self):
		for run in self.runs:
			for key in frappe.cache.get_keys(f"flow_run_*:{run}*"):
				frappe.cache.delete_value(key, make_keys=False)
		frappe.db.rollback()

	def _start(self, text: str = "hi") -> tuple[dict[str, Any], dict[str, Any]]:
		"""Start a turn in background mode; returns (api payload, the enqueued job's kwargs)."""
		with (
			patch("flow.api.api._background_available", return_value=True),
			patch("frappe.enqueue") as enqueue,
		):
			payload = start_run(text, agent=self.agent.name, stream=True, background=True)
		self.runs.append(payload["name"])
		return payload, self._job(enqueue)

	def _job(self, enqueue) -> dict[str, Any]:
		# Starting a chat also enqueues unrelated work (title generation); pick out the run.
		jobs = [c for c in enqueue.call_args_list if c.args and c.args[0] == "flow.lib.background.execute"]
		self.assertEqual(len(jobs), 1)
		kwargs = jobs[0].kwargs
		return {key: kwargs[key] for key in ("run_name", "stream", "kind", "answers")}

	def _execute(self, job: dict[str, Any], chat) -> list[dict[str, Any]]:
		"""Run the job as the worker would; returns what it pushed over realtime."""
		pushed: list[dict[str, Any]] = []
		with (
			patch.object(Model, "chat", new=chat),
			patch(
				"frappe.publish_realtime",
				side_effect=lambda event, record=None, **kw: event == background.EVENT and pushed.append(record),
			),
		):
			background.execute(**job)
		return pushed

	def _types(self, records: list[dict[str, Any]]) -> list[str]:
		return [record["event"]["type"] for record in records]

	def test_start_returns_at_once_and_enqueues_the_turn(self):
		payload, job = self._start()

		self.assertTrue(payload["background"])
		self.assertEqual(payload["event"]["type"], "run_started")
		self.assertEqual(payload["event"]["name"], payload["name"])
		self.assertEqual(job, {"run_name": payload["name"], "stream": payload["stream"], "kind": "start", "answers": None})
		self.assertEqual(frappe.db.get_value("Flow Run", payload["name"], "status"), "Running")
		self.assertTrue(background.is_alive(payload["name"]))

	def test_job_runs_the_turn_and_publishes_its_events(self):
		payload, job = self._start()

		pushed = self._execute(job, _stream_chat(["Hel", "lo"], _final("Hello")))

		self.assertEqual(self._types(pushed), ["text", "done"])
		self.assertEqual(pushed[0]["event"]["delta"], "Hello")  # deltas are batched
		self.assertEqual([record["seq"] for record in pushed], [1, 2])
		self.assertEqual(pushed[-1]["event"]["status"], "Completed")

		run = frappe.get_doc("Flow Run", payload["name"])
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.output, "Hello")
		session = frappe.get_doc("Flow Session", run.session)
		self.assertEqual([m.role for m in session.messages], ["system", "user", "assistant"])
		self.assertFalse(background.is_alive(payload["name"]))

	def test_events_can_be_polled_after_a_sequence_number(self):
		payload, job = self._start()
		self._execute(job, _stream_chat(["Hello"], _final("Hello")))

		everything = get_run_events(payload["name"], payload["stream"])
		self.assertEqual(self._types(everything["events"]), ["text", "done"])
		self.assertEqual(everything["status"], "Completed")
		self.assertFalse(everything["alive"])

		rest = get_run_events(payload["name"], payload["stream"], after=1)
		self.assertEqual(self._types(rest["events"]), ["done"])

	def test_events_are_private_to_the_run_owner(self):
		payload, job = self._start()
		self._execute(job, _stream_chat(["Hello"], _final("Hello")))
		other = frappe.get_doc(
			{"doctype": "User", "email": "bg-other@example.com", "first_name": "Other", "roles": [{"role": "Flow User"}]}
		).insert(ignore_permissions=True)

		frappe.set_user(other.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_run_events(payload["name"], payload["stream"])
		finally:
			frappe.set_user("Administrator")

	def test_model_failure_marks_the_run_failed_and_publishes_an_error(self):
		payload, job = self._start()

		def chat(self, messages, tools=None, *, stream=False):
			raise RuntimeError("provider down")

		pushed = self._execute(job, chat)

		self.assertEqual(self._types(pushed), ["error"])
		self.assertIn("provider down", pushed[0]["event"]["message"])
		self.assertEqual(frappe.db.get_value("Flow Run", payload["name"], "status"), "Failed")
		self.assertFalse(background.is_alive(payload["name"]))

	def test_stop_before_the_job_starts_skips_the_model(self):
		payload, job = self._start()
		stop_run(payload["name"])
		called: list[bool] = []

		def chat(self, messages, tools=None, *, stream=False):
			called.append(True)
			return _final("should not run")

		pushed = self._execute(job, chat)

		self.assertEqual(called, [])
		self.assertEqual(self._types(pushed), ["error"])
		run = frappe.get_doc("Flow Run", payload["name"])
		self.assertEqual((run.status, run.error), ("Failed", "Stopped by user."))

	def test_paused_run_resumes_in_the_background(self):
		payload, job = self._start("do it")
		pushed = self._execute(job, _stream_chat([], _confirm_call()))
		self.assertEqual(pushed[-1]["event"]["status"], "Paused")

		with (
			patch("flow.api.api._background_available", return_value=True),
			patch("frappe.enqueue") as enqueue,
		):
			resumed = resume_run(payload["name"], {"c1": "Deny"}, stream=True, background=True)
		resume_job = self._job(enqueue)

		self.assertEqual(resumed["name"], payload["name"])
		self.assertNotEqual(resumed["stream"], payload["stream"])
		self.assertEqual(resume_job["kind"], "resume")

		pushed = self._execute(resume_job, _stream_chat([], _final("unused")))
		self.assertEqual(self._types(pushed), ["tool_ended", "done"])
		self.assertEqual(frappe.db.get_value("Flow Run", payload["name"], "status"), "Completed")

	def test_a_dispatched_run_is_not_enqueued_twice(self):
		payload, _job = self._start()

		with patch("frappe.enqueue") as enqueue:
			stream = background.dispatch(payload["name"], kind="start")

		enqueue.assert_not_called()
		self.assertEqual(stream, payload["stream"])

	def test_active_run_is_found_until_the_job_ends(self):
		payload, job = self._start()
		chat = frappe.db.get_value("Flow Run", payload["name"], "session")

		self.assertEqual(
			get_active_run(chat), {"run": payload["name"], "stream": payload["stream"], "status": "Running"}
		)
		self._execute(job, _stream_chat(["ok"], _final("ok")))
		self.assertIsNone(get_active_run(chat))

	def test_a_live_run_is_not_recovered_as_abandoned(self):
		payload, _job = self._start()
		session = frappe.db.get_value("Flow Run", payload["name"], "session")
		frappe.db.set_value(
			"Flow Run", payload["name"], "creation", frappe.utils.add_to_date(None, hours=-1), update_modified=False
		)

		self.assertEqual(recover_session(session), {"recovered": 0})
		self.assertEqual(frappe.db.get_value("Flow Run", payload["name"], "status"), "Running")

		frappe.cache.delete_value(background._alive_key(payload["name"]))
		self.assertEqual(recover_session(session), {"recovered": 1})

	def test_falls_back_to_a_stream_when_no_worker_is_available(self):
		with (
			patch("flow.api.api._background_available", return_value=False),
			patch.object(Model, "chat", new=_stream_chat(["Hello"], _final("Hello"))),
		):
			response = start_run("hi", agent=self.agent.name, stream=True, background=True)

		self.assertIsInstance(response, Response)

	def test_background_is_off_when_disabled_in_site_config(self):
		with patch.dict(frappe.conf, {"flow_background_chat": 0}):
			self.assertFalse(background.is_available())

	def test_background_is_off_when_flow_settings_says_in_request(self):
		settings = frappe.get_single("Flow Settings")
		with patch("flow.lib.background.chat_queue", return_value="long"):
			self.assertTrue(background.is_available())

			settings.chat_run_mode = "In Request"
			settings.save()
			self.assertFalse(background.is_available())

			settings.chat_run_mode = "Background Job"
			settings.save()
			self.assertTrue(background.is_available())

	def test_a_run_stays_alive_while_a_tool_works_silently(self):
		payload, job = self._start()
		seen: list[bool] = []

		def slow_chat(self, messages, tools=None, *, stream=False):
			# No events for longer than the heartbeat TTL, like a long report or OCR.
			def gen():
				time.sleep(0.6)
				seen.append(background.is_alive(payload["name"]))
				yield "done"
				return _final("done")

			return gen()

		with (
			patch.object(background, "HEARTBEAT_INTERVAL", 0.1),
			patch.object(background, "HEARTBEAT_TTL", 0.3),
		):
			self._execute(job, slow_chat)

		self.assertEqual(seen, [True])
		self.assertFalse(background.is_alive(payload["name"]))
