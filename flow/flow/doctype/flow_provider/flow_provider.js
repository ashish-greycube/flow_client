// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Provider", {
	refresh(frm) {
		frm.add_custom_button(__("Connect with ChatGPT"), () => start_chatgpt_login(frm));
	},
});

function start_chatgpt_login(frm) {
	frappe.call({
		method: "flow.flow.doctype.flow_provider.flow_provider.start_chatgpt_login",
		freeze: true,
		freeze_message: __("Starting sign-in…"),
		callback: (r) => {
			if (!r.message) return;
			const { url, state } = r.message;
			window.open(url, "_blank", "noopener");
			poll_chatgpt_login(frm, state);
			show_paste_fallback(frm, state);
		},
	});
}

function poll_chatgpt_login(frm, state) {
	const interval = setInterval(async () => {
		const r = await frappe.call({
			method: "flow.flow.doctype.flow_provider.flow_provider.poll_chatgpt_login",
			args: { state },
		});
		const status = r.message && r.message.status;
		if (status === "connected") {
			clearInterval(interval);
			frappe.show_alert({ message: __("Connected with ChatGPT"), indicator: "green" });
			if (frm.doc.name === "codex") {
				frm.reload_doc();
			} else {
				frappe.set_route(["Form", "Flow Provider", "codex"]);
			}
		} else if (status === "failed" || status === "expired") {
			clearInterval(interval);
			frappe.show_alert({
				message: (r.message && r.message.message) || __("Sign-in failed"),
				indicator: "red",
			});
		}
	}, 2500);
}

function show_paste_fallback(frm, state) {
	// For when the local listener on port 1455 couldn't bind (remote bench, or
	// the port already held): the browser lands on a dead localhost URL that the
	// user can paste back here to finish the same exchange.
	const dialog = new frappe.ui.Dialog({
		title: __("Connect with ChatGPT"),
		fields: [
			{
				fieldname: "info",
				fieldtype: "HTML",
				options: `<p>${__(
					"A tab opened to sign in with ChatGPT. If it redirects to a page that fails to load, copy that page's address and paste it below."
				)}</p>`,
			},
			{
				fieldname: "redirect_url",
				fieldtype: "Data",
				label: __("Redirected URL"),
			},
		],
		primary_action_label: __("Connect"),
		primary_action: ({ redirect_url }) => {
			frappe.call({
				method: "flow.flow.doctype.flow_provider.flow_provider.finish_chatgpt_login",
				args: { redirect_url },
				freeze: true,
				callback: (r) => {
					if (r.message && r.message.status === "connected") {
						dialog.hide();
						frappe.show_alert({ message: __("Connected with ChatGPT"), indicator: "green" });
						if (frm.doc.name === "codex") {
							frm.reload_doc();
						} else {
							frappe.set_route(["Form", "Flow Provider", "codex"]);
						}
					} else {
						frappe.msgprint((r.message && r.message.message) || __("Sign-in failed"));
					}
				},
			});
		},
	});
	dialog.show();
}