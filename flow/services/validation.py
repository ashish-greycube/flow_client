# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""File validation for the extraction pipeline. Reusable by any Frappe app on this bench —
call `validate_file` before parsing/OCR-ing a File, the same check File2ERP runs at upload."""

from __future__ import annotations

import os

import frappe
from frappe import _

from flow.knowledge.extract import FILE_EXTENSIONS

DEFAULT_MAX_FILE_SIZE_MB = 25


def validate_file(file_doc) -> None:
	"""Raise if `file_doc` is an unsupported type or too large to process."""
	extension = os.path.splitext(file_doc.file_name or file_doc.file_url or "")[1].lower().lstrip(".")
	if extension not in FILE_EXTENSIONS:
		frappe.throw(_("Unsupported file type: .{0}").format(extension or "?"), title=_("Unsupported File"))

	max_mb = _max_file_size_mb()
	size = file_doc.file_size or 0
	if size > max_mb * 1024 * 1024:
		frappe.throw(_("File exceeds the {0} MB size limit.").format(max_mb), title=_("File Too Large"))


def _max_file_size_mb() -> int:
	try:
		settings = frappe.get_cached_doc("Flow File2ERP Settings")
		return int(settings.max_file_size_mb) or DEFAULT_MAX_FILE_SIZE_MB
	except Exception:
		return DEFAULT_MAX_FILE_SIZE_MB
