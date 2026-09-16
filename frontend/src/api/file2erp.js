// File2ERP: whitelisted flow.api.file2erp.* calls, following the same thin-wrapper
// convention as client.js (frappe.xcall(method, args) — no serialization of our own).

export const createFile2ERPEntry = (file) =>
	frappe.xcall("flow.api.file2erp.create_file2erp_entry", { file });

export const getFile2ERPEntry = (name) =>
	frappe.xcall("flow.api.file2erp.get_file2erp_entry", { name });

export const deleteFile2ERPEntry = (name) =>
	frappe.xcall("flow.api.file2erp.delete_file2erp_entry", { name });

// Confirms (or changes) document_type and enqueues extraction — the explicit trigger
// that replaces auto-start-on-upload; extraction is scoped to this DocType. `force`
// bypasses process_entry's own idempotency guard — the "Re-extract Data" action.
export const startExtraction = (name, document_type, force = false) =>
	frappe.xcall("flow.api.file2erp.start_extraction", { name, document_type, force });

export const listFile2ERPEntries = (filters, limit) =>
	frappe.xcall("flow.api.file2erp.list_file2erp_entries", { filters, limit });

export const updateFile2ERPData = (name, fields, line_items) =>
	frappe.xcall("flow.api.file2erp.update_file2erp_data", { name, fields, line_items });

// Stages this entry's already-extracted text as a chat attachment (no re-parsing).
// Returns the same { file, file_name, file_size } chip shape attachFile() does.
export const openChatSession = (name) =>
	frappe.xcall("flow.api.file2erp.open_chat_session", { name });

// Button-triggered shortcut: map + create directly, bypassing the chat. The caller
// must confirm with the user first — this has no agent-run approval pause of its own.
export const createDocumentFromEntry = (name, doctype, fields, line_items) =>
	frappe.xcall("flow.api.file2erp.create_document_from_entry", { name, doctype, fields, line_items });
