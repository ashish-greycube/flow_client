const getList = (doctype, options) =>
	frappe.xcall("frappe.client.get_list", { doctype, ...options });

export const loadTriggers = () =>
	getList("Flow Trigger", {
		fields: [
			"name",
			"title",
			"enabled",
			"agent",
			"event",
			"target_doctype",
			"doc_event",
			"cron_expression",
			"prompt_template",
			"last_fired_at",
			"modified",
		],
		order_by: "modified desc",
		limit_page_length: 500,
	});

export const loadTrigger = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Trigger", name });

export const loadTriggerRuns = (trigger) =>
	getList("Flow Run", {
		filters: { source: "Trigger", trigger },
		fields: [
			"name",
			"session",
			"status",
			"reference_doctype",
			"reference_name",
			"iterations",
			"input",
			"output",
			"error",
			"creation",
			"modified",
		],
		order_by: "creation desc",
		limit_page_length: 20,
	});

export const loadTriggerAgents = () =>
	getList("Flow Agent", {
		filters: { enabled: 1 },
		fields: ["name", "title"],
		order_by: "title asc",
		limit_page_length: 500,
	});

export const loadTriggerDoctypes = () =>
	getList("DocType", {
		filters: { istable: 0 },
		fields: ["name"],
		order_by: "name asc",
		limit_page_length: 1000,
	});

export const loadTriggerUsers = () =>
	getList("User", {
		filters: { enabled: 1, name: ["!=", "Guest"] },
		fields: ["name", "full_name"],
		order_by: "full_name asc",
		limit_page_length: 500,
	});

export const createTrigger = (doc) => frappe.xcall("frappe.client.insert", { doc });

export const updateTrigger = (name, values) =>
	frappe.xcall("frappe.client.set_value", {
		doctype: "Flow Trigger",
		name,
		fieldname: values,
	});

export const renameTrigger = (oldName, newName) =>
	frappe.xcall("frappe.client.rename_doc", {
		doctype: "Flow Trigger",
		old_name: oldName,
		new_name: newName,
	});
