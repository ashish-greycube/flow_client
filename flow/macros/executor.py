from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

MACRO = "Flow Macro"
MACRO_RUN = "Flow Macro Run"


@frappe.whitelist()
def run_macro(macro: str) -> dict[str, str]:
	doc = frappe.get_doc(MACRO, macro)
	_assert_owner(doc)
	if not doc.enabled:
		frappe.throw(_("This macro is disabled."))
	if not doc.steps:
		frappe.throw(_("This macro has no steps."))

	run = frappe.get_doc(
		{
			"doctype": MACRO_RUN,
			"macro": doc.name,
			"agent": doc.agent,
			"status": "Queued",
			"trigger": "Manual",
			"total_steps": len(doc.steps),
		}
	).insert(ignore_permissions=True)
	_assign_owner(run.doctype, run.name, doc.owner)
	frappe.enqueue(
		"flow.macros.executor.execute_macro",
		enqueue_after_commit=True,
		macro_run=run.name,
	)
	return {"macro_run": run.name, "status": run.status}


def execute_macro(macro_run: str) -> None:
	run = frappe.get_doc(MACRO_RUN, macro_run)
	if run.status not in ("Queued", "Running"):
		return
	macro = frappe.get_doc(MACRO, run.macro)
	if not macro.enabled:
		_finish(run, "Stopped", _("The macro was disabled before it started."))
		return
	if not _valid_run_user(macro.owner, unattended=run.trigger == "Scheduled"):
		_finish(run, "Failed", _("The macro owner is not an enabled System User."))
		return

	original_user = frappe.session.user
	frappe.set_user(macro.owner)
	try:
		_run_remaining_steps(run, macro)
	except Exception as exc:
		frappe.log_error(title=f"Flow Macro failed: {macro.name}", message=frappe.get_traceback())
		_finish(run, "Failed", str(exc))
	finally:
		frappe.set_user(original_user)


@frappe.whitelist()
def resume_macro_run(macro_run: str, answers: dict | str) -> dict[str, str]:
	run = frappe.get_doc(MACRO_RUN, macro_run)
	_assert_owner(run)
	if run.status != "Paused" or not run.session or not run.flow_run:
		frappe.throw(_("Only a paused macro run can be resumed."))
	if isinstance(answers, str):
		answers = json.loads(answers)
	if not isinstance(answers, dict):
		frappe.throw(_("Answers must be a JSON object."))

	from flow.lib.session import load_session

	flow_run = load_session(run.session).resume(answers)
	if flow_run.status == "Paused":
		return {"macro_run": run.name, "status": run.status, "flow_run": flow_run.name}
	if flow_run.status == "Failed":
		_finish(run, "Failed", flow_run.error)
		return {"macro_run": run.name, "status": run.status, "flow_run": flow_run.name}

	run.status = "Running"
	run.save(ignore_permissions=True)
	frappe.enqueue(
		"flow.macros.executor.execute_macro",
		enqueue_after_commit=True,
		macro_run=run.name,
	)
	return {"macro_run": run.name, "status": run.status, "flow_run": flow_run.name}


@frappe.whitelist()
def stop_macro_run(macro_run: str) -> dict[str, str]:
	run = frappe.get_doc(MACRO_RUN, macro_run)
	_assert_owner(run)
	if run.status not in ("Completed", "Failed", "Stopped"):
		_finish(run, "Stopped", _("Stopped by user."))
	return {"macro_run": run.name, "status": run.status}


def run_due_macros() -> None:
	now = now_datetime()
	due = frappe.get_all(
		MACRO,
		filters={"enabled": 1, "schedule_enabled": 1, "next_run_at": ["<=", now]},
		fields=["name", "owner", "schedule_frequency", "schedule_time"],
	)
	for row in due:
		try:
			_queue_scheduled(row, now)
		except Exception:
			frappe.log_error(title=f"Flow Macro schedule failed: {row.name}", message=frappe.get_traceback())


def _queue_scheduled(row, now) -> None:
	from flow.macros.schedule import compute_next_run

	if not _valid_run_user(row.owner, unattended=True):
		frappe.db.set_value(
			MACRO,
			row.name,
			{"next_run_at": compute_next_run(row.schedule_frequency, row.schedule_time, now)},
			update_modified=False,
		)
		return
	macro = frappe.get_doc(MACRO, row.name)
	run = frappe.get_doc(
		{
			"doctype": MACRO_RUN,
			"macro": macro.name,
			"agent": macro.agent,
			"status": "Queued",
			"trigger": "Scheduled",
			"total_steps": len(macro.steps),
		}
	).insert(ignore_permissions=True)
	_assign_owner(run.doctype, run.name, macro.owner)
	frappe.db.set_value(
		MACRO,
		macro.name,
		{
			"last_run_at": now,
			"next_run_at": compute_next_run(macro.schedule_frequency, macro.schedule_time, now),
		},
		update_modified=False,
	)
	frappe.enqueue("flow.macros.executor.execute_macro", enqueue_after_commit=True, macro_run=run.name)


def _run_remaining_steps(run, macro) -> None:
	from flow.lib.session import load_session, new_session

	steps = list(macro.steps or [])
	source = "Trigger" if run.trigger == "Scheduled" else "Manual"
	index = int(run.current_step or 0)
	if index >= len(steps):
		_finish(run, "Completed")
		return
	if not run.session:
		session = new_session(macro.agent, title=macro.macro_name, source=source)
		run.session = session.name
		run.started_at = now_datetime()
	else:
		session = load_session(run.session, agent=macro.agent)
	run.status = "Running"
	run.save(ignore_permissions=True)

	step = steps[index]
	model = step.model_override or frappe.db.get_value("Flow Agent", macro.agent, "model")
	session = load_session(session.name, agent=macro.agent, model=model)
	try:
		flow_run = session.chat(step.prompt, source=source, auto_approve=bool(macro.auto_approve))
	except Exception as exc:
		run.reload()
		if run.status == "Stopped":
			return
		run.current_step = index + 1
		if macro.stop_on_error:
			_finish(run, "Failed", str(exc))
			return
		run.error = str(exc)[:5000]
		run.save(ignore_permissions=True)
		_queue_next_step(run.name)
		return

	run.reload()
	if run.status == "Stopped":
		return
	run.current_step = index + 1
	run.flow_run = flow_run.name
	run.save(ignore_permissions=True)
	if flow_run.status == "Paused":
		run.status = "Paused"
		run.save(ignore_permissions=True)
		return
	if flow_run.status == "Failed" and macro.stop_on_error:
		_finish(run, "Failed", flow_run.error)
		return
	if run.current_step >= len(steps):
		_finish(run, "Completed")
		return
	_queue_next_step(run.name)


def _queue_next_step(macro_run: str) -> None:
	frappe.enqueue(
		"flow.macros.executor.execute_macro",
		enqueue_after_commit=True,
		macro_run=macro_run,
	)


def _finish(run, status: str, error: str | None = None) -> None:
	run.status = status
	run.finished_at = now_datetime()
	run.error = str(error)[:5000] if error else None
	run.save(ignore_permissions=True)


def _assign_owner(doctype: str, name: str, owner: str) -> None:
	if owner and owner != frappe.session.user:
		frappe.db.set_value(doctype, name, "owner", owner, update_modified=False)


def _assert_owner(doc) -> None:
	if doc.owner == frappe.session.user or frappe.session.user == "Administrator":
		return
	frappe.throw(_("You can only run or control your own macros."), frappe.PermissionError)


def _valid_run_user(user: str, *, unattended: bool) -> bool:
	if not user or user == "Guest" or (unattended and user == "Administrator"):
		return False
	if user == "Administrator":
		return True
	return bool(frappe.db.get_value("User", user, "enabled")) and frappe.db.get_value(
		"User", user, "user_type"
	) == "System User"
