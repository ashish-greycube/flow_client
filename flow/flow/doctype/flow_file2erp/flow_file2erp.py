# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
import os

import frappe
from frappe import _
from frappe.model.document import Document

JSON_FIELDS = ("extracted_fields", "extracted_line_items", "field_mapping")

# Extension -> coarse category shown in the list view / filters.
_FILE_TYPE_BY_EXTENSION = {
	"pdf": "PDF",
	"png": "Image",
	"jpg": "Image",
	"jpeg": "Image",
	"webp": "Image",
	"bmp": "Image",
	"tiff": "Image",
	"tif": "Image",
	"gif": "Image",
	"xlsx": "Excel",
	"docx": "Word",
	"doc": "Word",
	"pptx": "PowerPoint",
	"csv": "CSV",
	"tsv": "CSV",
}


class FlowFile2ERP(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ai_input: DF.LongText | None
		confidence: DF.Percent
		conversation: DF.Link | None
		created_document: DF.DynamicLink | None
		created_document_type: DF.Link | None
		document_type: DF.Literal["Expense Claim", "Sales Invoice", "Purchase Invoice", "Purchase Order", "Sales Order", "Payment Entry"]
		error: DF.LongText | None
		extracted_fields: DF.JSON | None
		extracted_line_items: DF.JSON | None
		field_mapping: DF.JSON | None
		file: DF.Link
		file_name: DF.Data | None
		file_size: DF.Int
		file_type: DF.Literal["PDF", "Image", "Excel", "Word", "CSV", "Text", "PowerPoint", "Other"]
		input_tokens: DF.Int
		output_tokens: DF.Int
		raw_text: DF.LongText | None
		status: DF.Literal["Uploaded", "Processing", "Extracted", "Needs Review", "Failed", "Document Created"]
		total_tokens: DF.Int
	# end: auto-generated types

	def validate(self):
		self._validate_json_fields()
		self._classify_file_type()

	def _validate_json_fields(self):
		for fieldname in JSON_FIELDS:
			value = self.get(fieldname)
			if value in (None, ""):
				continue
			if not isinstance(value, str):
				continue
			try:
				json.loads(value)
			except (TypeError, ValueError):
				frappe.throw(_("{0} must be valid JSON.").format(fieldname), title=_("Invalid JSON"))

	def _classify_file_type(self):
		if self.file_type and not self.has_value_changed("file"):
			return
		name = self.file_name or (frappe.db.get_value("File", self.file, "file_name") if self.file else "")
		extension = os.path.splitext(name or "")[1].lower().lstrip(".")
		self.file_type = _FILE_TYPE_BY_EXTENSION.get(extension, "Text" if extension else "Other")

	# Deliberately no after_insert auto-enqueue anymore: extraction is scoped to
	# document_type, so it must wait for the user to pick (or confirm) that DocType
	# first — see flow.api.file2erp.start_extraction, which enqueues
	# flow.services.file2erp.process_entry explicitly once that happens.
