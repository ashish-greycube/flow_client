frappe.pages["flow-chat"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Flow Chat"),
		single_column: true,
	});

	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty().css({ padding: 0, border: "none" });

	const root = $("<div>", { id: "flow-chat-root" })
		.css({
			height: "calc(100vh - var(--navbar-height) - var(--page-head-height) - 65px)",
			overflow: "hidden",
		})
		.appendTo($parent);

	frappe.require(
		["/assets/flow/flow_chat/flow_chat.css", "/assets/flow/flow_chat/flow_chat.js"],
		() => {
			if (window.mountFlowChat) window.mountFlowChat(root.attr("id"));
		}
	);
};
