# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from frappe.tests import UnitTestCase

from flow.agent_instructions import (
	DOCUMENT_WRITE_VALIDATION_INSTRUCTIONS,
	SALES_INVOICE_CREATION_INSTRUCTIONS,
	STRICT_AGENT_VALIDATION_INSTRUCTIONS,
)
from flow.assistant.assistant import ASSISTANT_INSTRUCTIONS
from flow.assistant.ocr_agent import OCR_AGENT_INSTRUCTIONS
from flow.fac_tools.prebuilt_agents import _instructions, _tool_names, load_prebuilt_catalog


class TestPrebuiltAgents(UnitTestCase):
	def test_every_agent_preserves_purpose_and_uses_strict_data_validation(self):
		for specification in load_prebuilt_catalog():
			instructions = _instructions(specification)
			self.assertIn(specification["description"], instructions)
			self.assertIn(STRICT_AGENT_VALIDATION_INSTRUCTIONS, instructions)

	def test_every_operator_uses_document_write_validation(self):
		for specification in load_prebuilt_catalog():
			instructions = _instructions(specification)
			if specification.get("writes"):
				self.assertIn(DOCUMENT_WRITE_VALIDATION_INSTRUCTIONS, instructions)
			else:
				self.assertNotIn(DOCUMENT_WRITE_VALIDATION_INSTRUCTIONS, instructions)

	def test_builtin_agents_use_shared_validation_contract(self):
		for instructions in (ASSISTANT_INSTRUCTIONS, OCR_AGENT_INSTRUCTIONS):
			self.assertIn(STRICT_AGENT_VALIDATION_INSTRUCTIONS, instructions)
			self.assertIn(DOCUMENT_WRITE_VALIDATION_INSTRUCTIONS, instructions)

	def test_ar_operator_uses_sales_invoice_skill_contract(self):
		specification = next(
			row for row in load_prebuilt_catalog() if row["agent_slug"] == "ar-collections-operator"
		)

		self.assertIn("Sales Invoice", specification["doctypes_required"])
		self.assertIn("Sales Invoice Item", specification["doctypes_required"])
		self.assertIn({"doctype": "Sales Invoice", "mode": "draft"}, specification["writes"])
		self.assertIn("create", _tool_names(specification))
		self.assertIn("update", _tool_names(specification))
		self.assertIn("most recent Sales Invoice", SALES_INVOICE_CREATION_INSTRUCTIONS)
		self.assertIn(
			"create call itself opens Flow's approval window", SALES_INVOICE_CREATION_INSTRUCTIONS
		)
		self.assertIn(SALES_INVOICE_CREATION_INSTRUCTIONS, _instructions(specification))
