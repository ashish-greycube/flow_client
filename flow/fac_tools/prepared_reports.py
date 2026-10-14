# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

"""Background (Prepared Report) handling for `generate_report`, adapted from Jarvis.

A Prepared Report is one too heavy to run inline: Frappe generates it in a `long`
queue job and stores the output on a `Prepared Report` doc. Running it inside the
agent turn instead holds the turn for minutes, so `generate_report` returns a status
the model relays, recomputed from live state on every ask:

- ready: a completed copy for these filters exists; its rows ride along with `as_of`.
- generating: a background run for these filters is queued or running.
- failed: the latest run errored; its reason is surfaced, and it is not retried until
  the filters change.
- started: a slow inline run moved to the background (see reports._run_inline).

So a repeated ask with the same filters reuses the completed copy instead of
running the report again.

Unlike Jarvis, Flow runs the whole agent loop inside one job, so two things differ:

- The job running this turn occupies a worker. With no idle worker on the `long`
  queue a background run could only start after the turn ends, so the report runs
  inline instead.
- A started or in-flight run is waited on for up to WAIT_SECONDS, once per turn. A
  later call in the same turn returns at once and tells the model to stop asking,
  so it can't poll in a loop until it runs out of iterations.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import frappe
from frappe.utils import cint

# Frappe's own budget for a prepared report job (prepared_report.REPORT_TIMEOUT);
# a report may override it with Report.timeout.
DEFAULT_REPORT_TIMEOUT = 25 * 60
# A Started run older than its timeout plus this margin lost its worker; run it again.
# A Queued run is never re-triggered on age: it waits for a worker, and starting a
# duplicate would only lengthen the `long` queue backlog.
STARTED_STALL_MARGIN = 5 * 60
# The caller's newest runs of one report compared by filter meaning (see _latest).
MATCH_SCAN = 50
REPORT_QUEUE = "long"
# How long one call waits for a background run to finish, and how often it checks.
WAIT_SECONDS = 45
POLL_SECONDS = 2
STOP_POLLING = (
	"Do not call generate_report again for this report in this reply: tell the user it is "
	"being prepared in the background and that asking again later with the same request "
	"returns the results, then end your reply."
)


def is_prepared(report_name: str) -> bool:
	"""Read the flag from the Report row itself; a Custom Report carries its own."""
	return bool(frappe.db.get_value("Report", report_name, "prepared_report"))


def worker_available() -> bool:
	"""Whether an idle worker listens on the queue prepared reports run on. A busy one
	may be running this very turn, and a run queued behind it starts only after the
	turn ends."""
	if frappe.flags.in_test:
		return True
	try:
		from frappe.utils.background_jobs import generate_qname, get_redis_conn
		from rq import Worker

		queue = generate_qname(REPORT_QUEUE)
		return any(
			queue in worker.queue_names() and worker.get_state() == "idle"
			for worker in Worker.all(get_redis_conn())
		)
	except Exception:
		return False


def handle(
	report_name: str, filters: dict[str, Any], definitions: list[dict[str, Any]]
) -> dict[str, Any] | None:
	"""Return the ready / generating / failed state for this user and filters, or None
	when nothing is stored and no worker is free to generate it now, so the caller runs
	the report inline. `filters` already carries the report's defaults (apply_defaults)."""
	from frappe.desk.query_report import validate_filters_permissions

	user = frappe.session.user
	# run() checks that Link filter values are readable; this path bypasses run().
	validate_filters_permissions(report_name, filters, user, js_filters=definitions)
	filters = _canonical(filters)
	_refresh()

	completed = _latest(report_name, filters, user, ("Completed",))
	if completed:
		ready = _read_completed(completed.name)
		if ready is not None:
			return ready

	pending = _pending(report_name, filters, user)
	if pending is not None and pending["status"] == "failed":
		return pending
	if not worker_available():
		return None
	if pending is None:
		pending = start(report_name, filters)
	return _wait(report_name, filters, pending["run"])


def start(report_name: str, filters: dict[str, Any], message: str | None = None) -> dict[str, Any]:
	"""Start a background run and return the `started` state."""
	from frappe.core.doctype.prepared_report.prepared_report import make_prepared_report

	run = make_prepared_report(report_name, _canonical(filters))["name"]
	# The job is enqueued after commit; commit now so it starts while the turn goes on.
	if not frappe.flags.in_test:
		frappe.db.commit()
	return _status(
		report_name,
		"started",
		(message or "This report runs in the background and has been started.") + " " + STOP_POLLING,
		run=run,
	)


def _wait(report_name: str, filters: dict[str, Any], run: str) -> dict[str, Any]:
	"""Wait for `run` up to WAIT_SECONDS, once per turn for these filters: a repeated
	call in the same turn returns at once, so the model can't poll in a loop."""
	key = f"{report_name}:{_match_key(filters)}"
	waited = frappe.flags.flow_report_waits = frappe.flags.flow_report_waits or set()
	if key not in waited:
		waited.add(key)
		deadline = time.monotonic() + WAIT_SECONDS
		while time.monotonic() < deadline:
			time.sleep(POLL_SECONDS)
			status = _run_status(run)
			if status == "Completed":
				ready = _read_completed(run)
				if ready is not None:
					return ready
				break
			if status == "Error":
				return _failed(report_name, run)
	return _generating(report_name, run)


def _run_status(run: str) -> str | None:
	_refresh()
	return frappe.db.get_value("Prepared Report", run, "status")


def _refresh() -> None:
	"""End the transaction so the next read sees what the report job committed since:
	under REPEATABLE READ a long turn keeps reading its first snapshot."""
	if not frappe.flags.in_test:
		frappe.db.commit()


def _canonical(filters: dict[str, Any]) -> dict[str, Any]:
	"""Drop empty values so the run we start is the run our lookup finds."""
	return {key: value for key, value in filters.items() if value not in (None, "")}


def _latest(report_name: str, filters: dict[str, Any], user: str, statuses: tuple[str, ...]):
	"""The user's newest run of this report in one of `statuses` for the same filters.

	Matched on meaning, not Frappe's stored JSON: a run started from Desk stores its
	own value types (1 for true, a multi-select in its own order)."""
	want = _match_key(filters)
	rows = frappe.get_all(
		"Prepared Report",
		filters={"report_name": report_name, "owner": user, "status": ("in", statuses)},
		fields=["name", "filters", "status", "creation"],
		order_by="creation desc",
		limit=MATCH_SCAN,
		# Owner-scoped: a normal user lacks the Prepared Report read role.
		ignore_permissions=True,
	)
	for row in rows:
		try:
			stored = json.loads(row.filters or "{}")
		except (TypeError, ValueError):
			continue
		if isinstance(stored, dict) and _match_key(stored) == want:
			return row
	return None


def _match_key(filters: dict[str, Any]) -> str:
	def normalize(value):
		if isinstance(value, bool):
			value = int(value)
		if isinstance(value, float) and value.is_integer():
			value = int(value)
		if isinstance(value, list | tuple):
			return sorted(str(normalize(item)) for item in value)
		return str(value)

	return json.dumps(
		{key: normalize(value) for key, value in filters.items() if not _unset(value)}, sort_keys=True
	)


def _unset(value: Any) -> bool:
	"""Desk sends only filters that have a value: blank, 0, "%" or an empty list read as unset."""
	if isinstance(value, list | tuple):
		return not value
	return value is None or value in ("", "%") or (isinstance(value, int | float) and value == 0)


def _read_completed(name: str) -> dict[str, Any] | None:
	"""The `ready` state from a completed run's stored output, or None when the output
	can't be read, so the caller runs the report again rather than answer empty."""
	try:
		doc = frappe.get_doc("Prepared Report", name)
		raw = doc.get_prepared_data()
		data = json.loads(raw.decode("utf-8")) if raw else None
	except frappe.DoesNotExistError:
		return None
	except Exception as e:
		frappe.log_error(
			title=f"Flow: prepared report output unreadable ({name})",
			message=f"{type(e).__name__} reading prepared report {name}",
		)
		return None
	if isinstance(data, dict):
		output = data
	elif isinstance(data, list):
		# Older prepared reports stored the bare rows and kept columns on the doc.
		output = {"result": data, "columns": json.loads(doc.columns) if doc.get("columns") else []}
	else:
		return None
	if not isinstance(output.get("result") or [], list):
		return None
	as_of = doc.get("report_end_time") or doc.creation
	return _status(
		doc.report_name,
		"ready",
		f"Results of the background run generated {as_of}; the figures are as of that time.",
		run=name,
		as_of=str(as_of),
		output=output,
	)


def _pending(report_name: str, filters: dict[str, Any], user: str) -> dict[str, Any] | None:
	"""State of the newest unfinished run: `generating` while it is in flight, `failed`
	if it errored, or None (nothing pending, or a Started run lost its worker)."""
	row = _latest(report_name, filters, user, ("Queued", "Started", "Error"))
	if not row:
		return None
	if row.status == "Queued":
		return _generating(report_name, row.name)
	if row.status == "Started":
		age = frappe.utils.time_diff_in_seconds(frappe.utils.now(), row.creation)
		if age <= _report_timeout(report_name) + STARTED_STALL_MARGIN:
			return _generating(report_name, row.name)
		return None
	# Re-running the same failing job on every ask would loop; changed filters make a
	# new match key and so a fresh run.
	return _failed(report_name, row.name)


def _failed(report_name: str, run: str) -> dict[str, Any]:
	reason = _error_reason(frappe.db.get_value("Prepared Report", run, "error_message"))
	return _status(
		report_name,
		"failed",
		f"The background run of this report failed: {reason}. Correct the filters (see "
		"report_requirements) and call generate_report again; changed filters start a new run.",
		run=run,
		error=reason,
	)


def _error_reason(traceback: str | None) -> str:
	"""The exception message from the last line of a traceback, without its class name."""
	lines = [line.strip() for line in (traceback or "").splitlines() if line.strip()]
	if not lines:
		return "unknown error (see the Error Log)"
	return re.sub(r"^[\w.]*(?:Error|Exception)\w*:\s*", "", lines[-1])[:300]


def _generating(report_name: str, run: str) -> dict[str, Any]:
	return _status(
		report_name,
		"generating",
		f"This report is still being generated in the background. {STOP_POLLING}",
		run=run,
	)


def _report_timeout(report_name: str) -> int:
	return cint(frappe.db.get_value("Report", report_name, "timeout")) or DEFAULT_REPORT_TIMEOUT


def _status(report_name: str, status: str, message: str, **extra: Any) -> dict[str, Any]:
	return {
		"success": True,
		"report_name": report_name,
		"prepared_report": True,
		"status": status,
		"message": message,
		**extra,
	}
