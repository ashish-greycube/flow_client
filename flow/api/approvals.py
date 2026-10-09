# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Trigger Approval Board: trigger runs paused on a confirmation tool, and approving or
denying them so the run continues in the background."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from flow.auth import require_flow_user
from flow.triggers.triggers import TRIGGER_QUEUE, TRIGGER_TIMEOUT

DECISIONS = ("Approve", "Deny")


@frappe.whitelist()
def get_trigger_approvals() -> list[dict[str, Any]]:
	"""Paused trigger runs the current user can act on, oldest first."""
	require_flow_user()
	runs = frappe.get_list(
		"Flow Run",
		filters={"source": "Trigger", "status": "Paused"},
		fields=["name", "session", "trigger", "reference_doctype", "reference_name", "input", "questions", "creation", "owner"],
		order_by="creation asc",
		limit_page_length=200,
	)
	trigger_titles = _titles("Flow Trigger", {run.trigger for run in runs})
	session_agents = _session_agents({run.session for run in runs})
	for run in runs:
		run.questions = json.loads(run.questions) if run.questions else []
		run.trigger_title = trigger_titles.get(run.trigger) or run.trigger
		run.agent = session_agents.get(run.session)
		run.needs_confirmation = _all_confirmations(run.questions)
	return runs


@frappe.whitelist()
def decide_trigger_approval(run_name: str, decision: str) -> dict[str, str]:
	"""Approve or deny every pending tool call of a paused trigger run, then resume it."""
	require_flow_user()
	from flow.lib.session import assert_run_owner

	if decision not in DECISIONS:
		frappe.throw(_("Decision must be Approve or Deny."), title=_("Invalid Decision"))
	run = frappe.get_doc("Flow Run", run_name)
	assert_run_owner(run)
	if run.source != "Trigger" or run.status != "Paused":
		frappe.throw(_("This run is no longer waiting for approval."), title=_("Cannot Resume"))
	questions = json.loads(run.questions) if run.questions else []
	if not _all_confirmations(questions):
		frappe.throw(_("This run is waiting for an answer, not an approval. Open it in chat."))

	answers = {question["key"]: decision for question in questions}
	run.add_comment("Info", _("{0} from the Trigger Approval Board by {1}").format(decision, frappe.session.user))
	frappe.enqueue(
		"flow.api.approvals.resume_trigger_run",
		queue=TRIGGER_QUEUE,
		timeout=TRIGGER_TIMEOUT,
		enqueue_after_commit=True,
		job_id=f"flow-trigger-approval::{run.name}",
		deduplicate=True,
		run_name=run.name,
		answers=answers,
	)
	return {"run": run.name, "decision": decision}


def resume_trigger_run(run_name: str, answers: dict[str, str]) -> None:
	"""Worker: resume the paused run as the user the trigger ran as, like flow.triggers.fire."""
	from flow.lib.session import load_session

	run = frappe.get_doc("Flow Run", run_name)
	if run.status != "Paused":
		return
	original_user = frappe.session.user
	in_flow_trigger = frappe.flags.in_flow_trigger
	frappe.set_user(run.owner)
	frappe.flags.in_flow_trigger = True
	try:
		load_session(run.session).resume(answers)
	except Exception:
		frappe.log_error(title=f"Flow trigger approval resume failed: {run_name}")
	finally:
		frappe.flags.in_flow_trigger = in_flow_trigger
		frappe.set_user(original_user)


def _all_confirmations(questions: list[dict[str, Any]]) -> bool:
	return bool(questions) and all(
		question.get("key") and set(DECISIONS) <= set(question.get("options") or []) for question in questions
	)


def _titles(doctype: str, names: set[str]) -> dict[str, str]:
	names.discard(None)
	if not names:
		return {}
	rows = frappe.get_all(doctype, filters={"name": ["in", list(names)]}, fields=["name", "title"])
	return {row.name: row.title for row in rows}


def _session_agents(sessions: set[str]) -> dict[str, str]:
	sessions.discard(None)
	if not sessions:
		return {}
	rows = frappe.get_all("Flow Session", filters={"name": ["in", list(sessions)]}, fields=["name", "agent"])
	return {row.name: row.agent for row in rows}
