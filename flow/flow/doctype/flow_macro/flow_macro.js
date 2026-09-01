frappe.ui.form.on("Flow Macro", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.enabled) {
			frm.add_custom_button(__("Run Macro"), () => {
				frappe.call({
					method: "flow.macros.executor.run_macro",
					args: { macro: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message?.macro_run) {
							frappe.set_route("Form", "Flow Macro Run", r.message.macro_run);
						}
					},
				});
			});
		}
	},
});
