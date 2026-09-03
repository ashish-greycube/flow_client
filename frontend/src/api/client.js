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

export const loadTools = () =>
	getList("Flow Tool", {
		filters: { enabled: 1 },
		fields: ["name", "title"],
		order_by: "title asc",
		limit_page_length: 500,
	});

export const loadKnowledgeBases = () =>
	getList("Flow Knowledge Base", {
		filters: { enabled: 1 },
		fields: ["name", "title"],
		order_by: "title asc",
		limit_page_length: 500,
	});

// Full CRUD for the Agents page's create/edit dialog — plain frappe.client
// calls (the same generic whitelisted methods this file already uses
// elsewhere), so no new server-side endpoint is needed.
export const getAgent = (name) => frappe.xcall("frappe.client.get", { doctype: "Flow Agent", name });

export const createAgent = (values) =>
	frappe.xcall("frappe.client.insert", { doc: { doctype: "Flow Agent", ...values } });

// `frappe.client.set_value` can't touch table fields ("Cannot edit standard
// fields" aside, it never rebuilds child rows), which the Tools/Knowledge
// Bases fields need — so updates go through `frappe.client.save` instead,
// same as a Desk form's Save button. That means `doc` must carry the FULL
// document state (frappe.get_doc(dict) builds the doc from exactly what's
// given, it does not merge onto the existing DB row), not just the changed
// fields — the caller is responsible for including every field it cares
// about (is_system_generated included, or a save would silently clear it).
// Title is still never the thing that changes docname here — Flow Agent is
// `autoname: "field:title"`, so an actual rename (renameAgent below) has to
// happen first when the title changed.
export const saveAgent = (doc) => frappe.xcall("frappe.client.save", { doc: { doctype: "Flow Agent", ...doc } });

// Renames the document (Flow Agent's title IS its name — see saveAgent's
// note). Returns the name actually used, which can differ slightly from
// `newTitle` if it needed sanitizing.
export const renameAgent = (oldName, newTitle) =>
	frappe.xcall("frappe.client.rename_doc", {
		doctype: "Flow Agent",
		old_name: oldName,
		new_name: newTitle,
	});

// Full catalog for the Knowledge Base page — every knowledge base regardless
// of enabled state, with the fields needed for its card.
export const loadAllKnowledgeBases = () =>
	getList("Flow Knowledge Base", {
		fields: ["name", "title", "enabled", "is_system_generated", "description"],
		order_by: "title asc",
		limit_page_length: 500,
	});

export const getKnowledgeBase = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Knowledge Base", name });

export const createKnowledgeBase = (values) =>
	frappe.xcall("frappe.client.insert", { doc: { doctype: "Flow Knowledge Base", ...values } });

export const saveKnowledgeBase = (doc) =>
	frappe.xcall("frappe.client.save", { doc: { doctype: "Flow Knowledge Base", ...doc } });

export const renameKnowledgeBase = (oldName, newTitle) =>
	frappe.xcall("frappe.client.rename_doc", {
		doctype: "Flow Knowledge Base",
		old_name: oldName,
		new_name: newTitle,
	});

// Sources linked to one knowledge base (the Desk form's "Connections" tab
// equivalent — Flow Knowledge Source has no doctype of its own field back
// onto Flow Knowledge Base besides this `knowledge_base` Link).
export const loadKnowledgeSources = (knowledgeBase) =>
	getList("Flow Knowledge Source", {
		filters: { knowledge_base: knowledgeBase },
		fields: [
			"name",
			"title",
			"source_type",
			"status",
			"chunk_count",
			"is_system_generated",
			"modified",
		],
		order_by: "creation desc",
		limit_page_length: 500,
	});

export const getKnowledgeSource = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Knowledge Source", name });

export const createKnowledgeSource = (values) =>
	frappe.xcall("frappe.client.insert", { doc: { doctype: "Flow Knowledge Source", ...values } });

export const saveKnowledgeSource = (doc) =>
	frappe.xcall("frappe.client.save", { doc: { doctype: "Flow Knowledge Source", ...doc } });

// Flow Knowledge Source's `resync`/`reconcile` are plain whitelisted Document
// methods (flow_knowledge_source.py) — called the same generic way Desk's own
// `frm.call()` does (frappe/public/js/frappe/form/controls/button.js), rather
// than adding a dedicated endpoint for each.
export const resyncKnowledgeSource = (name, rebuild = false) =>
	frappe.xcall("run_doc_method", {
		dt: "Flow Knowledge Source",
		dn: name,
		method: "resync",
		args: { rebuild: rebuild ? 1 : 0 },
	});

export const reconcileKnowledgeSource = (name) =>
	frappe.xcall("run_doc_method", { dt: "Flow Knowledge Source", dn: name, method: "reconcile" });

// For the "Reference DocType" picker (DocType-source knowledge sources) — every
// non-child doctype, the same universe Desk's own Link field for `options:
// "DocType"` searches against.
export const loadReferenceDoctypes = () =>
	getList("DocType", {
		filters: { istable: 0 },
		fields: ["name"],
		order_by: "name asc",
		limit_page_length: 5000,
	});

export const loadHistory = () => frappe.xcall("flow.api.get_chat_history");

export const searchSessions = (query) => frappe.xcall("flow.api.get_chat_history", { query });

export const getSession = (name) => frappe.xcall("flow.api.get_chat", { name });

export const getPausedRun = (name) => frappe.xcall("flow.api.get_chat_paused_run", { name });

// Feedback the user already gave on this session's runs, to restore thumbs state on reload.
export const getRunFeedback = (name) => frappe.xcall("flow.api.get_chat_feedback", { name });

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
