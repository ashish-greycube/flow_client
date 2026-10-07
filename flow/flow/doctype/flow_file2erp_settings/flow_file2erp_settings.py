# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class FlowFile2ERPSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		default_document_type: DF.Literal["Expense Claim", "Sales Invoice", "Purchase Invoice", "Purchase Order", "Sales Order", "Payment Entry"]
		extraction_model: DF.Link
		max_file_size_mb: DF.Int
	# end: auto-generated types

	def validate(self):
		if cint(self.max_file_size_mb) < 1:
			frappe.throw(_("Max File Size must be at least 1 MB."), title=_("Invalid Setting"))
		# Flow doesn't require ERPNext/HRMS — refuse a default that every new upload
		# would then fail to create.
		if self.default_document_type and not frappe.db.exists("DocType", self.default_document_type):
			frappe.throw(
				_("{0} is not installed on this site.").format(self.default_document_type),
				title=_("Invalid Setting"),
			)
