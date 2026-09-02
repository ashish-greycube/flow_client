const getList = (doctype, options) =>
	frappe.xcall("frappe.client.get_list", { doctype, ...options });

export const loadMacros = () =>
	getList("Flow Macro", {
		fields: [
			"name",
			"macro_name",
			"description",
			"agent",
			"enabled",
			"schedule_enabled",
			"next_run_at",
			"owner",
			"modified",
		],
		order_by: "modified desc",
		limit_page_length: 100,
	});

export const loadMacro = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Macro", name });

export const loadMacroRun = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Macro Run", name });

export const loadMacroAgents = () =>
	getList("Flow Agent", {
		filters: { enabled: 1 },
		fields: ["name", "title"],
		order_by: "title asc",
		limit_page_length: 100,
	});

export const createMacro = (doc) => frappe.xcall("frappe.client.insert", { doc });

export const saveMacro = (doc) => frappe.xcall("frappe.client.save", { doc });

export const runMacro = (macro) => frappe.xcall("flow.macros.executor.run_macro", { macro });

export const stopMacroRun = (macro_run) =>
	frappe.xcall("flow.macros.executor.stop_macro_run", { macro_run });
