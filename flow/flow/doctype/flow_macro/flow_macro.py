from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

MAX_MACROS_PER_OWNER = 25
MAX_NAME_LENGTH = 80
MAX_DESCRIPTION_LENGTH = 500
MAX_STEPS = 25
MAX_PROMPT_LENGTH = 5000


class FlowMacro(Document):
	def on_trash(self):
		frappe.db.delete("Flow Macro Run", {"macro": self.name})

	def validate(self):
		self._validate_content()
		self._validate_owner_limits()
		self._guard_auto_approve()
		self._set_next_run()

	def _validate_content(self):
		self.macro_name = (self.macro_name or "").strip()
		self.description = (self.description or "").strip()
		if not self.macro_name:
			frappe.throw(_("Macro Name is required."))
		if len(self.macro_name) > MAX_NAME_LENGTH:
			frappe.throw(_("Macro Name must be at most {0} characters.").format(MAX_NAME_LENGTH))
		if len(self.description) > MAX_DESCRIPTION_LENGTH:
			frappe.throw(_("Description must be at most {0} characters.").format(MAX_DESCRIPTION_LENGTH))
		if not self.steps:
			frappe.throw(_("A macro needs at least one step."))
		if len(self.steps) > MAX_STEPS:
			frappe.throw(_("A macro can have at most {0} steps.").format(MAX_STEPS))
		for index, step in enumerate(self.steps, start=1):
			step.label = (step.label or "").strip()
			step.prompt = (step.prompt or "").strip()
			if not step.prompt:
				frappe.throw(_("Step {0} has an empty prompt.").format(index))
			if len(step.prompt) > MAX_PROMPT_LENGTH:
				frappe.throw(
					_("Step {0} prompt must be at most {1} characters.").format(index, MAX_PROMPT_LENGTH)
				)

	def _validate_owner_limits(self):
		owner = self.owner or frappe.session.user
		duplicate = frappe.db.exists(
			"Flow Macro",
			{"owner": owner, "macro_name": self.macro_name, "name": ["!=", self.name or ""]},
		)
		if duplicate:
			frappe.throw(_("You already have a macro named {0}.").format(self.macro_name))
		if self.is_new() and frappe.db.count("Flow Macro", {"owner": owner}) >= MAX_MACROS_PER_OWNER:
			frappe.throw(_("You can have at most {0} macros.").format(MAX_MACROS_PER_OWNER))

	def _guard_auto_approve(self):
		if not self.auto_approve:
			return
		previous = self.get_doc_before_save()
		if previous and previous.auto_approve:
			return
		if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
			frappe.throw(
				_("Only a System Manager can enable unattended tool approval."),
				frappe.PermissionError,
			)

	def _set_next_run(self):
		from flow.macros.schedule import (
			compute_next_run,
			validate_cron_expression,
			validate_schedule_time,
		)

		if not self.schedule_enabled:
			self.next_run_at = None
			return
		if self.schedule_frequency == "Cron":
			validate_cron_expression(self.cron_expression)
		else:
			validate_schedule_time(self.schedule_time)
		if (
			self.is_new()
			or self.has_value_changed("schedule_enabled")
			or self.has_value_changed("schedule_frequency")
			or self.has_value_changed("schedule_time")
			or self.has_value_changed("cron_expression")
			or not self.next_run_at
		):
			self.next_run_at = compute_next_run(
				self.schedule_frequency,
				self.schedule_time,
				cron_expression=self.cron_expression,
			)


def on_doctype_update():
	frappe.db.add_index("Flow Macro", ["owner", "macro_name"], index_name="owner_macro_name_index")
