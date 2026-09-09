# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _

SLASH_COMMAND = re.compile(r"^/([a-z0-9]+(?:-[a-z0-9]+)*)(?:\s|$)")


def resolve_invocation(input: str, skill: str | None = None) -> Any | None:
	"""Resolve an explicit skill or a slash command at the start of the input."""
	match = SLASH_COMMAND.match(input.lstrip())
	command = match.group(1) if match else None
	if skill and command and skill.removeprefix("/") != command:
		frappe.throw(
			_("The selected skill does not match the /{0} command.").format(command),
			title=_("Skill Mismatch"),
		)

	name = (skill or command or "").removeprefix("/")
	if not name:
		return None
	if not frappe.db.exists("Flow Skill", name):
		frappe.throw(_("Unknown skill command /{0}.").format(name), title=_("Skill Not Found"))

	doc = frappe.get_doc("Flow Skill", name)
	frappe.has_permission("Flow Skill", "read", doc.name, throw=True)
	if not doc.enabled:
		frappe.throw(_("Skill /{0} is disabled.").format(doc.command), title=_("Disabled Skill"))
	return doc
