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

// Mirrors Flow File2ERP's own document_type Select options (flow_file2erp.json).
export const FILE2ERP_DOCUMENT_TYPES = [
	"Expense Claim",
	"Sales Invoice",
	"Purchase Invoice",
	"Purchase Order",
	"Sales Order",
	"Payment Entry",
	"Lead",
];
// Only an Expense Claim combines several files into one document (many receipts, one claim).
export const COMBINABLE_DOCUMENT_TYPES = ["Expense Claim"];

// Several just-uploaded files at once: mode "separate" (one document per file) or
// "combined" (one Expense Claim for all of them, reviewed on the batch page).
export const startBatch = (entries, document_type, mode) =>
	frappe.xcall("flow.api.file2erp.start_batch", { entries, document_type, mode });

export const getFile2ERPBatch = (batch) =>
	frappe.xcall("flow.api.file2erp.get_file2erp_batch", { batch });

export const removeFromBatch = (name) =>
	frappe.xcall("flow.api.file2erp.remove_from_batch", { name });

// Like createDocumentFromEntry, the caller must confirm with the user first.
export const createCombinedExpenseClaim = (batch, fields, line_items) =>
	frappe.xcall("flow.api.file2erp.create_combined_expense_claim", { batch, fields, line_items });
