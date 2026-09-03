# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe.model.document import Document


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
	def clear_old_logs(days: int = 90) -> None:
		cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
		for name in frappe.get_all("Flow Conversation", filters={"modified": ["<", cutoff]}, pluck="name"):
			frappe.delete_doc("Flow Conversation", name, ignore_permissions=True, force=True)
