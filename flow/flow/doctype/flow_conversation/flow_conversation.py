# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe.model.document import Document

CHAT_RETENTION_DAYS = 90


class FlowConversation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		routing_mode: DF.Literal["Auto", "Manual"]
		title: DF.Data | None
	# end: auto-generated types

	def on_trash(self) -> None:
		"""Delete agent-specific segments through their controllers so files and indexes are cleaned."""
		for session in frappe.get_all("Flow Session", filters={"conversation": self.name}, pluck="name"):
			frappe.delete_doc("Flow Session", session, ignore_permissions=True, force=True)

	@staticmethod
	def clear_old_logs(days: int = CHAT_RETENTION_DAYS) -> None:
		"""Delete conversations created more than `days` ago, regardless of recent activity."""
		cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
		for name in frappe.get_all("Flow Conversation", filters={"creation": ["<", cutoff]}, pluck="name"):
			frappe.delete_doc("Flow Conversation", name, ignore_permissions=True, force=True)
			frappe.db.commit()


def chat_retention_cutoff(doctype: str = "Flow Conversation") -> str:
	"""Creation datetime before which chats of `doctype` are expired, per Log Settings."""
	days = frappe.db.get_value(
		"Logs To Clear", {"parent": "Log Settings", "ref_doctype": doctype}, "days"
	) or CHAT_RETENTION_DAYS
	return frappe.utils.add_days(frappe.utils.now(), -int(days))
