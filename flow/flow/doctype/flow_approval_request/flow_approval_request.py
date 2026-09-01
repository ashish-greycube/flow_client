# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class FlowApprovalRequest(Document):
	"""A human decision requested by a Flow agent."""

	def validate(self):
		self._guard_decision_fields()
		self._set_decision_audit()
		if self.status != "Pending" and not self.decision:
			frappe.throw("A decided approval request must include the decision text.")

	def on_update(self):
		self._leave_reference_comment()

	def _guard_decision_fields(self) -> None:
		if self.flags.ignore_permissions or frappe.session.user == "Administrator":
			return
		if self.is_new() and (
			(self.status or "Pending") != "Pending" or self.decision or self.decided_by or self.decided_at
		):
			frappe.throw("A new approval request must be pending and undecided.", frappe.PermissionError)
		if self.has_value_changed("decided_by") and self.decided_by != frappe.session.user:
			frappe.throw("Decided By must be the current user.", frappe.PermissionError)

	def _set_decision_audit(self) -> None:
		if self.status == "Pending" or not self.decision:
			return
		if not self.decided_by:
			self.decided_by = frappe.session.user
		if not self.decided_at:
			self.decided_at = now_datetime()

	def _leave_reference_comment(self) -> None:
		if (
			self.status == "Pending"
			or self.trace_comment_added
			or not (self.ref_doctype and self.ref_name)
			or not frappe.db.exists(self.ref_doctype, self.ref_name)
		):
			return
		decider = self.decided_by or frappe.session.user
		if not (
			frappe.has_permission(self.ref_doctype, "read", self.ref_name, user=decider)
			and frappe.has_permission(self.ref_doctype, "write", self.ref_name, user=decider)
		):
			return
		comment = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": self.ref_doctype,
				"reference_name": self.ref_name,
				"content": (
					f"Flow Approval Request <b>{self.name}</b> "
					f"({frappe.utils.escape_html(self.title or '')}): "
					f"<b>{self.status}</b> - {frappe.utils.escape_html(self.decision or '')}"
				),
				"comment_email": decider,
				"comment_by": frappe.utils.get_fullname(decider),
			}
		)
		comment.insert(ignore_permissions=True)
		frappe.db.set_value("Comment", comment.name, "owner", decider, update_modified=False)
		self.db_set("trace_comment_added", 1, update_modified=False)
