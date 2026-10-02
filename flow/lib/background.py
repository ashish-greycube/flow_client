# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Run a chat turn in a background job instead of inside the web request.

A streamed turn holds its web request open for the whole run, so on a production
bench it is killed at the gunicorn timeout and pins a web worker meanwhile. Here
the request only records the turn and enqueues `execute`; the job runs the agent
and hands each event to the browser two ways:

- pushed over realtime, so text appears as it is produced, and
- appended to a short-lived Redis list the browser polls, so nothing is lost when
  the socket is down or an event is dropped.

A heartbeat key marks a dispatched run as alive, from enqueue until the job ends.
It stops a long but healthy run from being treated as abandoned, and its value (the
stream id) lets a reloaded page find the run and follow it again.
"""

from __future__ import annotations

import json
import time
from typing import Any

import frappe
from frappe import _

EVENT = "flow_run_event"
CHAT_QUEUE = "flow_chat"
FALLBACK_QUEUE = "long"
JOB_TIMEOUT = 600
# How long a dispatched run may wait for a worker before it counts as abandoned.
QUEUED_TTL = 300
# Refreshed while the job runs; must outlast the longest gap between two events.
HEARTBEAT_TTL = 180
HEARTBEAT_INTERVAL = 15
EVENTS_TTL = 900
# Text deltas arrive per token; they are sent in batches of roughly this many seconds.
TEXT_FLUSH_SECONDS = 0.15


def is_available() -> bool:
	"""Whether a turn can run in the background right now. False sends the caller back
	to the in-request stream, so chat keeps working on a bench with no worker.

	Off when Flow Settings says "In Request", or when site config sets
	`flow_background_chat` to 0 (an override that works without opening the desk)."""
	if not frappe.utils.cint(frappe.conf.get("flow_background_chat", 1)):
		return False
	# Never saved means the field default: Background Job.
	mode = frappe.db.get_single_value("Flow Settings", "chat_run_mode", cache=True)
	if mode == "In Request":
		return False
	return chat_queue() is not None


def chat_queue() -> str | None:
	"""The queue chat turns go to: `flow_chat_queue` from site config if set, else a
	dedicated `flow_chat` queue when the bench declares one, else `long`. None when no
	worker is listening on it."""
	override = (frappe.conf.get("flow_chat_queue") or "").strip()
	if override:
		candidates = [override]
	else:
		declared = frappe.get_conf().get("workers") or {}
		candidates = [CHAT_QUEUE, FALLBACK_QUEUE] if CHAT_QUEUE in declared else [FALLBACK_QUEUE]

	try:
		from frappe.utils.background_jobs import generate_qname, get_redis_conn
		from rq import Worker

		listening = {name for worker in Worker.all(get_redis_conn()) for name in worker.queue_names()}
		return next((q for q in candidates if generate_qname(q) in listening), None)
	except Exception:
		return None


def dispatch(run_name: str, *, kind: str, answers: dict[str, Any] | None = None) -> str:
	"""Enqueue the job for a recorded turn (`kind="start"`) or for resuming a paused one
	(`kind="resume"`). Returns the stream id the browser follows. A run that is already
	dispatched is not enqueued twice; its existing stream id is returned."""
	existing = active_stream(run_name)
	if existing:
		return existing

	stream = frappe.generate_hash(length=12)
	frappe.cache.set_value(_alive_key(run_name), stream, expires_in_sec=QUEUED_TTL)
	frappe.cache.delete_value(_stop_key(run_name))
	frappe.enqueue(
		"flow.lib.background.execute",
		queue=chat_queue() or FALLBACK_QUEUE,
		timeout=JOB_TIMEOUT,
		# A person is waiting on this; don't sit behind scheduled work on a shared queue.
		at_front=True,
		enqueue_after_commit=True,
		run_name=run_name,
		stream=stream,
		kind=kind,
		answers=answers,
	)
	return stream


def execute(run_name: str, stream: str, kind: str, answers: dict[str, Any] | None = None) -> None:
	"""Job: run the turn and publish its events. Runs as the user who sent the message."""
	from flow.flow.doctype.flow_run.flow_run import Error, RunStarted
	from flow.lib.session import load_session

	publisher = _Publisher(run_name, stream)
	try:
		run = frappe.get_doc("Flow Run", run_name)
		expected = "Running" if kind == "start" else "Paused"
		if stop_requested(run_name) or run.status != expected:
			publisher.send(Error(message=_("This run was stopped before it started.")))
			return

		session = load_session(run.session)
		events = session.stream_run(run) if kind == "start" else session.resume(answers or {}, stream=True)
		for event in events:
			# The request already returned this to the browser.
			if isinstance(event, RunStarted):
				continue
			publisher.send(event)
			if stop_requested(run_name):
				events.close()
				break
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(title="Flow background run failed")
		_mark_failed_if_running(run_name, str(e))
		publisher.send(Error(message=str(e)))
	finally:
		publisher.close()
		frappe.flags.flow_run = None


def events_after(run_name: str, stream: str, after: int = 0) -> list[dict[str, Any]]:
	"""Published events of a stream with a sequence number above `after`, oldest first."""
	# seq starts at 1 and events are appended in order, so list index == seq - 1.
	raw = frappe.cache.lrange(_events_key(run_name, stream), max(int(after), 0), -1)
	return [json.loads(item) for item in raw or []]


def active_stream(run_name: str) -> str | None:
	"""Stream id of a run that is queued or running in the background, else None."""
	return frappe.cache.get_value(_alive_key(run_name), use_local_cache=False) or None


def is_alive(run_name: str) -> bool:
	return active_stream(run_name) is not None


def request_stop(run_name: str) -> None:
	"""Ask the job to stop at its next event. Harmless when no job is running."""
	frappe.cache.set_value(_stop_key(run_name), 1, expires_in_sec=JOB_TIMEOUT)


def stop_requested(run_name: str) -> bool:
	return bool(frappe.cache.get_value(_stop_key(run_name), use_local_cache=False))


class _Publisher:
	"""Hands a job's events to the browser, batching text deltas."""

	def __init__(self, run_name: str, stream: str) -> None:
		self.run_name = run_name
		self.stream = stream
		self.user = frappe.session.user
		self.seq = 0
		self.text: list[str] = []
		self.last_flush = time.monotonic()
		self.last_beat = 0.0
		self._beat()

	def send(self, event: Any) -> None:
		from flow.api.api import _event_to_dict

		payload = _event_to_dict(event)
		if payload["type"] == "text":
			self.text.append(payload["delta"])
			if time.monotonic() - self.last_flush >= TEXT_FLUSH_SECONDS:
				self.flush()
			return
		self.flush()
		self._emit(payload)

	def flush(self) -> None:
		if self.text:
			delta, self.text = "".join(self.text), []
			self._emit({"type": "text", "delta": delta})
		self.last_flush = time.monotonic()

	def close(self) -> None:
		try:
			self.flush()
			frappe.cache.expire_key(_events_key(self.run_name, self.stream), EVENTS_TTL)
		finally:
			frappe.cache.delete_value(_alive_key(self.run_name))
			frappe.cache.delete_value(_stop_key(self.run_name))

	def _emit(self, payload: dict[str, Any]) -> None:
		self.seq += 1
		record = {"run": self.run_name, "stream": self.stream, "seq": self.seq, "event": payload}
		key = _events_key(self.run_name, self.stream)
		frappe.cache.rpush(key, json.dumps(record, default=str))
		if self.seq == 1:
			frappe.cache.expire_key(key, EVENTS_TTL)
		try:
			frappe.publish_realtime(EVENT, record, user=self.user)
		except Exception:
			# The browser still gets the event from the list when it polls.
			pass
		if time.monotonic() - self.last_beat >= HEARTBEAT_INTERVAL:
			self._beat()

	def _beat(self) -> None:
		frappe.cache.set_value(_alive_key(self.run_name), self.stream, expires_in_sec=HEARTBEAT_TTL)
		self.last_beat = time.monotonic()


def _mark_failed_if_running(run_name: str, error: str) -> None:
	"""A run the job could not even start streaming must not stay Running."""
	if frappe.db.get_value("Flow Run", run_name, "status") != "Running":
		return
	frappe.db.set_value(
		"Flow Run", run_name, {"status": "Failed", "error": (error or "Run failed.")[:5000]}
	)
	frappe.db.commit()


def _alive_key(run_name: str) -> str:
	return f"flow_run_alive:{run_name}"


def _stop_key(run_name: str) -> str:
	return f"flow_run_stop:{run_name}"


def _events_key(run_name: str, stream: str) -> str:
	return f"flow_run_events:{run_name}:{stream}"
