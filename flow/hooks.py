app_name = "flow"
app_title = "Flow"
app_publisher = "Shrihari Mahabal"
app_description = "Frappe Flow — native AI agents, tools, and triggers for Frappe"
app_email = "shriharimahabal08@gmail.com"
app_license = "agpl-3.0"

export_python_type_annotations = True

# Vite-built (frontend/src) AI panel bundle. Served directly from public/ — the
# /assets path bypasses the desk's esbuild pipeline. Run `yarn build` in the app root.
# /assets URLs get no cache-busting query from Frappe, so append ?v=<mtime>:
# the stable filename keeps the hook simple while a rebuild invalidates the cache.
import os as _os


def _flow_panel_asset(filename: str) -> str:
	path = _os.path.join(_os.path.dirname(__file__), "public", "flow_panel", filename)
	try:
		version = int(_os.path.getmtime(path))
	except OSError:
		version = 0
	return f"/assets/flow/flow_panel/{filename}?v={version}"


# Disabled: the slide-in panel (Ctrl+I) has been replaced by the full-page
# Flow Chat UI (see flow/flow/page/flow_chat). Re-enable by uncommenting these
# two lines if the overlay panel is needed again.
# app_include_js = [_flow_panel_asset("flow_panel.js")]
# app_include_css = [_flow_panel_asset("flow_panel.css")]

doc_events = {
	"Flow Model": {
		"after_insert": "flow.fac_tools.prebuilt_agents.sync_after_model_insert",
	},
	"*": {
		"after_insert": "flow.triggers.dispatch",
		"on_update": "flow.triggers.dispatch",
		"on_submit": "flow.triggers.dispatch",
		"on_cancel": "flow.triggers.dispatch",
		"on_trash": "flow.triggers.dispatch",
	}
}

permission_query_conditions = {
	"Flow Macro": "flow.macros.permissions.macro_query_conditions",
	"Flow Macro Run": "flow.macros.permissions.macro_run_query_conditions",
}

has_permission = {
	"Flow Macro": "flow.macros.permissions.has_macro_permission",
	"Flow Macro Run": "flow.macros.permissions.has_macro_run_permission",
}

# Flow's references to other docs are bookkeeping — they must never block deleting
# the referenced doc. A knowledge chunk indexes a doc; a Flow Run records the doc a
# trigger acted on. The incremental sweep removes orphaned chunks afterwards.
# A session's Flow Model reference is historical bookkeeping and must not block deletion.
ignore_links_on_delete = ["Flow Knowledge Chunk", "Flow Macro Run", "Flow Run", "Flow Session"]

default_log_clearing_doctypes = {
	"Flow Session": 90,
}

scheduler_events = {
	"daily": [
		"flow.knowledge.ingest.sync_due_sources",
	],
	"cron": {
		"*/5 * * * *": [
			"flow.triggers.dispatch_scheduled",
			"flow.macros.executor.run_due_macros",
		],
	},
}

after_migrate = [
	"flow.assistant.sync_builtin_assistant",
	"flow.fac_tools.sync_fac_tools",
]

extend_bootinfo = "flow.boot.boot_session"
