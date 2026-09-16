# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from flow.flow.doctype.flow_session.flow_session import derive_title
from flow.lib.session import _assert_session_owner

HANDOFF_MAX_CHARS = 4000
HANDOFF_MESSAGE_CHARS = 700
HANDOFF_MESSAGE_COUNT = 6


def create_conversation(input: str, routing_mode: str, *, title: str | None = None):
	frappe.has_permission("Flow Conversation", "create", throw=True)
	conversation = frappe.get_doc(
		{
			"doctype": "Flow Conversation",
			"title": title or derive_title(input),
			"routing_mode": routing_mode,
		}
	).insert()
	# The naive title above (first-line truncation) shows instantly; refine it in the
	# background into a short, meaning-based one — skipped when the caller supplied its
	# own title (e.g. adopt_session, which has no real first prompt to summarize).
	if not title and input.strip():
		from flow.routing.title import enqueue_title

		enqueue_title("Flow Conversation", conversation.name, input.strip(), None)
	return conversation


def adopt_session(session, routing_mode: str):
	"""Put a legacy manual session under a conversation when Auto is enabled after upgrade."""
	conversation = create_conversation("", routing_mode, title=session.title or session.name)
	session.db_set("conversation", conversation.name)
	return conversation


def resolve_chat(name: str):
	"""Return (conversation or None, active Flow Session), accepting legacy session ids."""
	if frappe.db.exists("Flow Conversation", name):
		conversation = frappe.get_doc("Flow Conversation", name)
		_assert_conversation_owner(conversation)
		session_name = frappe.db.get_value(
			"Flow Session", {"conversation": conversation.name}, "name", order_by="creation desc"
		)
		if not session_name:
			frappe.throw(_("This conversation has no session."), title=_("Invalid Conversation"))
		return conversation, frappe.get_doc("Flow Session", session_name)
	session = frappe.get_doc("Flow Session", name)
	_assert_session_owner(session)
	if session.conversation:
		conversation = frappe.get_doc("Flow Conversation", session.conversation)
		_assert_conversation_owner(conversation)
		return conversation, _active_session(conversation.name)
	return None, session


def get_chat(name: str) -> dict[str, Any]:
	conversation, active = resolve_chat(name)
	if not conversation:
		return active.as_dict()

	sessions = _conversation_sessions(conversation.name)
	messages: list[dict[str, Any]] = []
	attachments: list[dict[str, Any]] = []
	run_names: set[str] = set()
	for session in sessions:
		for row in session.messages:
			item = row.as_dict()
			item["agent"] = session.agent
			item["agent_session"] = session.name
			messages.append(item)
			if row.run:
				run_names.add(row.run)
		for row in session.attachments:
			item = row.as_dict()
			item["agent_session"] = session.name
			attachments.append(item)
	return {
		"name": conversation.name,
		"title": conversation.title,
		"routing_mode": conversation.routing_mode,
		"agent": active.agent,
		"model": active.model,
		"agent_session": active.name,
		"messages": messages,
		"attachments": attachments,
		"run_errors": _failed_run_errors(run_names),
	}


def _failed_run_errors(run_names: set[str]) -> dict[str, str]:
	"""Map run name -> its stored error, for runs that failed. A turn whose stream died
	mid-flight leaves no assistant reply in the transcript; this lets the client show the
	real reason instead of a generic "interrupted" placeholder."""
	if not run_names:
		return {}
	rows = frappe.get_all(
		"Flow Run",
		filters={"name": ["in", list(run_names)], "status": "Failed"},
		fields=["name", "error"],
	)
	return {row.name: row.error for row in rows if row.error}


def chat_history(query: str | None = None) -> list[dict[str, Any]]:
	conversation_filters: dict[str, Any] = {"owner": frappe.session.user}
	legacy_filters: dict[str, Any] = {
		"owner": frappe.session.user,
		"source": ["!=", "Trigger"],
		"conversation": ["is", "not set"],
	}
	if query:
		like = ["like", f"%{_escape_like(query)}%"]
		conversation_filters["title"] = like
		legacy_filters["title"] = like
	rows = frappe.get_list(
		"Flow Conversation",
		filters=conversation_filters,
		fields=["name", "title", "modified"],
		order_by="modified desc",
		limit_page_length=20,
	)
	rows += frappe.get_list(
		"Flow Session",
		filters=legacy_filters,
		fields=["name", "title", "modified"],
		order_by="modified desc",
		limit_page_length=20,
	)
	return sorted((dict(row) for row in rows), key=lambda row: row["modified"], reverse=True)[:20]


def conversation_context(conversation: str | None, session) -> list[dict[str, str]]:
	rows = []
	for segment in _conversation_sessions(conversation) if conversation else [session]:
		for message in segment.messages:
			if message.role in {"user", "assistant"} and message.content:
				rows.append({"role": message.role, "content": message.content})
	return rows[-HANDOFF_MESSAGE_COUNT:]


def build_handoff(context: list[dict[str, str]]) -> str:
	"""Build a bounded, factual handoff without another model call."""
	lines = ["Recent conversation context from the previous specialist:"]
	for message in context[-HANDOFF_MESSAGE_COUNT:]:
		content = " ".join(message["content"].split())[:HANDOFF_MESSAGE_CHARS]
		lines.append(f"- {message['role'].title()}: {content}")
	return "\n".join(lines)[:HANDOFF_MAX_CHARS]


def touch_conversation(conversation) -> None:
	if conversation:
		conversation.db_set("modified", frappe.utils.now(), update_modified=False)


def chat_sessions(name: str) -> list[str]:
	conversation, session = resolve_chat(name)
	if not conversation:
		return [session.name]
	return [row.name for row in _conversation_sessions(conversation.name)]


def delete_chat(name: str) -> None:
	"""Delete a conversation (its agent segments cascade via on_trash) or a legacy session."""
	conversation, session = resolve_chat(name)
	target = conversation or session
	frappe.delete_doc(target.doctype, target.name, ignore_permissions=True)


def _active_session(conversation: str):
	name = frappe.db.get_value("Flow Session", {"conversation": conversation}, "name", order_by="creation desc")
	return frappe.get_doc("Flow Session", name)


def _conversation_sessions(conversation: str | None) -> list[Any]:
	if not conversation:
		return []
	names = frappe.get_all(
		"Flow Session", filters={"conversation": conversation}, pluck="name", order_by="creation asc"
	)
	return [frappe.get_doc("Flow Session", name) for name in names]


def _assert_conversation_owner(doc) -> None:
	if doc.owner == frappe.session.user:
		return
	if frappe.has_permission("Flow Conversation", "write", doc):
		return
	frappe.throw(_("Not permitted to use this conversation."), frappe.PermissionError)


def _escape_like(value: str) -> str:
	return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
