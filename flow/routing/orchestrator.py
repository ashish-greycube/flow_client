# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING

from flow.lib.session import load_session, new_session
from flow.routing.conversation import (
	adopt_session,
	build_handoff,
	conversation_context,
	create_conversation,
	resolve_chat,
	touch_conversation,
)
from flow.routing.selector import RoutingDecision, select_agent

if TYPE_CHECKING:
	from flow.flow.doctype.flow_session.flow_session import FlowSession


def resolve_turn(
	input: str,
	agent: str | None,
	session: str | None,
	model: str | None,
	routing: str | None,
) -> tuple[FlowSession, RoutingDecision]:
	"""Resolve one API turn to an immutable agent-specific session."""
	if not routing:
		convo = load_session(session, agent=agent, model=model) if session else new_session(agent, model=model)
		return convo, RoutingDecision("Manual", convo.agent, 1.0, "")

	conversation = None
	current = None
	if session:
		conversation, current = resolve_chat(session)
		current._assert_not_blocked()
		if not conversation:
			conversation = adopt_session(current, routing.title())
	else:
		conversation = create_conversation(input, routing.title())

	if routing == "manual":
		return _manual_turn(agent, model, conversation, current)

	context = conversation_context(conversation.name, current) if current else []
	decision = _routing_decision(input, agent, model, current, context)
	if current and decision.agent == current.agent:
		convo = load_session(current.name, model=model)
	else:
		convo = new_session(
			decision.agent,
			model=model,
			title=conversation.title,
			conversation=conversation.name,
			previous_session=current.name if current else None,
			routing_action=decision.action,
			routing_confidence=decision.confidence,
			routing_reason=decision.reason,
			handoff_summary=build_handoff(context) if current else None,
		)
	touch_conversation(conversation)
	return convo, decision


def _manual_turn(agent, model, conversation, current) -> tuple[FlowSession, RoutingDecision]:
	if current:
		convo = load_session(current.name, agent=agent, model=model)
	else:
		convo = new_session(
			agent,
			model=model,
			title=conversation.title,
			conversation=conversation.name,
			routing_action="Manual",
		)
	decision = RoutingDecision("Manual", convo.agent, 1.0, "The user selected the agent manually.")
	touch_conversation(conversation)
	return convo, decision


def _routing_decision(input, agent, model, current, context) -> RoutingDecision:
	if agent:
		return RoutingDecision(
			"Continue" if current and current.agent == agent else ("Switch" if current else "Initial"),
			agent,
			1.0,
			"The user selected the agent explicitly.",
		)
	return select_agent(
		input,
		current_agent=current.agent if current else None,
		context=context,
		model=model,
	)
