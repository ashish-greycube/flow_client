frappe.ui.form.on("Flow Macro Run", {
	refresh(frm) {
		if (frm.doc.status === "Paused" && frm.doc.flow_run) {
			frm.add_custom_button(__("Open Pending Flow Run"), () => {
				frappe.set_route("Form", "Flow Run", frm.doc.flow_run);
			});
		}
		if (["Queued", "Running", "Paused"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Stop"), () => {
				frappe.call({
					method: "flow.macros.executor.stop_macro_run",
					args: { macro_run: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
