# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from flow.auth import is_flow_user
from flow.knowledge.extract import FILE_EXTENSIONS


def boot_session(bootinfo):
	# Single source of truth for file types the ingest pipeline can extract
	bootinfo.flow_supported_file_types = sorted(FILE_EXTENSIONS)
	# Gates the floating chat widget (frontend/src/main.js) — the API endpoints it
	# calls are restricted server-side regardless, this just keeps the launcher from
	# rendering for users who couldn't use it anyway.
	bootinfo.flow_user = is_flow_user()
