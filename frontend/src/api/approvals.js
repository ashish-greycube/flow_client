export const loadTriggerApprovals = () =>
	frappe.xcall("flow.api.approvals.get_trigger_approvals");

export const decideTriggerApproval = (run_name, decision) =>
	frappe.xcall("flow.api.approvals.decide_trigger_approval", { run_name, decision });
