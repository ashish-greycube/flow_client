# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

from flow.utils.system_generated import block_delete, validate_immutable

if TYPE_CHECKING:
	from flow.flow.doctype.flow_skill_tool.flow_skill_tool import FlowSkillTool
	from flow.lib.agent import Agent

COMMAND_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class FlowSkill(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		command: DF.Data
		description: DF.SmallText
		enabled: DF.Check
		instructions: DF.LongText
		is_system_generated: DF.Check
		title: DF.Data
		tools: DF.TableMultiSelect[FlowSkillTool]
	# end: auto-generated types

	def validate(self) -> None:
		self._normalize()
		self._validate_command()
		self._validate_tools()
		validate_immutable(self, fields=("command",))

	def on_trash(self) -> None:
		block_delete(self)

	def _normalize(self) -> None:
		for fieldname in ("title", "command", "description", "instructions"):
			value = self.get(fieldname)
			if isinstance(value, str):
				self.set(fieldname, value.strip())
		if self.command:
			self.command = self.command.removeprefix("/").lower()

	def _validate_command(self) -> None:
		if not COMMAND_PATTERN.fullmatch(self.command or ""):
			frappe.throw(
				_("Command must use lowercase letters, numbers, and single hyphens only."),
				title=_("Invalid Skill Command"),
			)
		if not self.is_new() and self.name != self.command:
			frappe.throw(_("A skill command cannot be changed after creation."), title=_("Command Locked"))

	def _validate_tools(self) -> None:
		selected = [row.tool for row in self.tools]
		if len(selected) != len(set(selected)):
			frappe.throw(_("A tool can be added to a skill only once."), title=_("Duplicate Tool"))

	def snapshot(self) -> dict[str, Any]:
		return {
			"name": self.name,
			"title": self.title,
			"command": self.command,
			"instructions": self.instructions,
			"tools": [row.tool for row in self.tools],
		}

	def apply(self, runtime: Agent) -> Agent:
		return apply_skill_snapshot(runtime, self.snapshot())


def apply_skill_snapshot(runtime: Agent, snapshot: dict[str, Any]) -> Agent:
	"""Build a run-local agent whose tools are a subset of the base agent's tools."""
	from flow.lib.agent import Agent

	tools_by_name = {tool.name: tool for tool in runtime.tools}
	selected = snapshot.get("tools") or []
	missing = sorted(set(selected) - set(tools_by_name))
	if missing:
		frappe.throw(
			_("Skill tools are unavailable on this agent: {0}").format(", ".join(missing)),
			title=_("Skill Configuration Error"),
		)
	return Agent(
		model=runtime.model,
		name=runtime.name,
		instructions=runtime.instructions,
		tools=[tools_by_name[name] for name in selected],
		max_iterations=runtime.max_iterations,
	)


def instruction_block(snapshot: dict[str, Any]) -> str:
	return (
		f"ACTIVE SKILL /{snapshot['command']} ({snapshot['title']})\n"
		"Treat the following as task-specific system instructions for this run only. "
		"They do not grant permissions or tools beyond those supplied to you.\n"
		f"{snapshot['instructions']}"
	)
