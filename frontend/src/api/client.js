import { __ } from "@/lib/translate";

// Read-only data fetches over the desk's whitelisted client API.
function getList(doctype, options) {
	return frappe.xcall("frappe.client.get_list", { doctype, ...options });
}

export const loadAgents = () =>
	getList("Flow Agent", {
		filters: { enabled: 1 },
		fields: ["name", "title"],
		limit_page_length: 50,
	});

// Full agent catalog for the Agents page (Featured/Enabled/Disabled tabs +
// search) — every agent regardless of enabled state, with the fields needed
// to render a card. Flow has no human-facing "description" field on Flow
// Agent, so the card falls back to a truncated `instructions` (the LLM
// system prompt) — the closest thing to one that already exists.
// `frappe.client.get_list` only recognizes `limit_page_length` (default 20)
// — a plain `limit` kwarg is silently dropped, which capped this at 20 rows.
export const loadAllAgents = () =>
	getList("Flow Agent", {
		fields: ["name", "title", "enabled", "is_system_generated", "model", "instructions"],
		order_by: "title asc",
		limit_page_length: 500,
	});

export const loadModels = () =>
	getList("Flow Model", {
		filters: { enabled: 1 },
		fields: ["name", "title"],
		limit_page_length: 50,
	});

// Full CRUD for the Agents page's create/edit dialog — plain frappe.client
// calls (the same generic whitelisted methods this file already uses
// elsewhere), so no new server-side endpoint is needed.
export const getAgent = (name) => frappe.xcall("frappe.client.get", { doctype: "Flow Agent", name });

export const createAgent = (values) =>
	frappe.xcall("frappe.client.insert", { doc: { doctype: "Flow Agent", ...values } });

// `fieldname` as a dict of {field: value} updates every key in one call.
// Title is deliberately never included here — Flow Agent is `autoname:
// "field:title"`, so the title field is locked in sync with the docname on
// every save (Document._sync_autoname_field) and silently reverts any other
// value written to it this way. Changing the title has to go through an
// actual rename (renameAgent below), which updates the docname and the
// field together.
export const updateAgent = (name, values) =>
	frappe.xcall("frappe.client.set_value", { doctype: "Flow Agent", name, fieldname: values });

// Renames the document (Flow Agent's title IS its name — see updateAgent's
// note). Returns the name actually used, which can differ slightly from
// `newTitle` if it needed sanitizing.
export const renameAgent = (oldName, newTitle) =>
	frappe.xcall("frappe.client.rename_doc", {
		doctype: "Flow Agent",
		old_name: oldName,
		new_name: newTitle,
	});

export const loadHistory = () =>
	getList("Flow Session", {
		filters: { owner: frappe.session.user, source: ["!=", "Trigger"] },
		fields: ["name", "title", "modified"],
		order_by: "modified desc",
		limit_page_length: 15,
	});

// Escape LIKE wildcards so a literal % or _ matches itself, not "anything".
const escapeLike = (s) => s.replace(/[\\%_]/g, "\\$&");

export const searchSessions = (query) =>
	getList("Flow Session", {
		filters: {
			owner: frappe.session.user,
			source: ["!=", "Trigger"],
			title: ["like", `%${escapeLike(query)}%`],
		},
		fields: ["name", "title", "modified"],
		order_by: "modified desc",
		limit_page_length: 20,
	});

export const getSession = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Session", name });

export const getPausedRun = (session) =>
	getList("Flow Run", {
		filters: { session, status: "Paused" },
		fields: ["name", "questions"],
		order_by: "creation desc",
		limit_page_length: 1,
	});

// Feedback the user already gave on this session's runs, to restore thumbs state on reload.
export const getRunFeedback = (session) =>
	getList("Flow Run", {
		filters: { session, feedback_rating: ["is", "set"] },
		fields: ["name", "feedback_rating", "feedback_comment"],
		limit_page_length: 100,
	});

// Record thumbs feedback on a run; optionally store a Down comment as agent memory.
export const submitFeedback = (args) => frappe.xcall("flow.api.submit_feedback", args);

// Fail any Running run left behind by a stream that was cut off (refresh/navigation),
// so a reloaded session isn't blocked from starting the next turn.
export const recoverSession = (session) => frappe.xcall("flow.api.recover_session", { session });

// Stop a run at the user's request: finalize an aborted stream's run or terminate a
// paused run so the agent won't continue.
export const stopRun = (run_name) => frappe.xcall("flow.api.stop_run", { run_name });

// Map of the agent's tool slugs → requires_confirmation, so the panel can tell an
// approval tool call from an inline one.
export const getAgentTools = (agent) => frappe.xcall("flow.api.get_agent_tools", { agent });

// Per-tool permission rows for the agent's Tool Permissions dialog: [{ tool, title,
// requires_confirmation, permission }], `permission` null unless explicitly overridden.
export const getAgentToolPermissions = (agent) =>
	frappe.xcall("flow.api.get_agent_tool_permissions", { agent });

// Bulk-set per-agent tool permission overrides. `permissions` maps tool slug →
// "Always Allow" | "Needs Approval" | "Blocked" | "" (clears the override).
export const setAgentToolPermissions = (agent, permissions) =>
	frappe.xcall("flow.api.set_agent_tool_permissions", { agent, permissions });

// "Save as macro": turns the conversation's user prompts into a new Flow Macro.
// `steps` is [{ label, prompt }, ...] in order. Returns the created macro's name.
export const createMacroFromPrompts = (agent, macro_name, steps) =>
	frappe.xcall("flow.api.create_macro_from_prompts", { agent, macro_name, steps });

// Upload a file as private, returning the created File doc. The chat attachment
// flow needs the File name to stage it via attachFile.
export async function uploadFile(file) {
	const form = new FormData();
	form.append("file", file, file.name);
	form.append("is_private", "1");

	const resp = await fetch("/api/method/upload_file", {
		method: "POST",
		headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
		body: form,
	});
	const data = await resp.json().catch(() => ({}));
	if (!resp.ok) throw new Error(serverMessage(data) || __("Upload failed ({0})", [resp.status]));
	return data.message;
}

// Validate and stage an uploaded File for use as a chat attachment. Returns chip
// metadata; throws (unsupported type, unreadable, …) which surfaces on the chip.
export const attachFile = (file) => frappe.xcall("flow.api.attach_file", { file });

// Extract the human-readable message from a frappe error body.
export function serverMessage(data) {
	try {
		const msgs = JSON.parse(data._server_messages || "[]");
		if (msgs.length) return JSON.parse(msgs[0]).message;
	} catch {
		// fall through to other error fields
	}
	return data.exception || data._error_message || null;
}
