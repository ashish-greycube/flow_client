frappe.pages["flow-chat"].on_page_load = function (wrapper) {
	ensureImmersiveStyle();

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Flow Chat"),
		single_column: true,
	});

	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty().css({ padding: 0, border: "none" });

	const root = $("<div>", { id: "flow-chat-root" })
		.css({ overflow: "hidden" })
		.appendTo($parent);

	frappe.require(
		["/assets/flow/flow_chat/flow_chat.css", "/assets/flow/flow_chat/flow_chat.js"],
		() => {
			if (window.mountFlowChat) window.mountFlowChat(root.attr("id"));
		},
	);
};

function ensureImmersiveStyle() {
	if (document.getElementById("flow-chat-immersive-style")) return;

	const style = document.createElement("style");
	style.id = "flow-chat-immersive-style";
	style.textContent = `
		body[data-route^="flow-chat"] {
			overflow: hidden !important;
		}
		body[data-route^="flow-chat"] header.navbar,
		body[data-route^="flow-chat"] .navbar,
		body[data-route^="flow-chat"] .page-head,
		body[data-route^="flow-chat"] .body-sidebar-container {
			display: none !important;
		}
		body[data-route^="flow-chat"] .main-section {
			height: 100vh !important;
			height: 100dvh !important;
			overflow: hidden !important;
			padding-top: 0 !important;
		}
		body[data-route^="flow-chat"] .page-container,
		body[data-route^="flow-chat"] .page-body,
		body[data-route^="flow-chat"] .layout-main,
		body[data-route^="flow-chat"] .layout-main-section-wrapper,
		body[data-route^="flow-chat"] .layout-main-section {
			height: 100% !important;
			min-height: 0 !important;
			margin-top: 0 !important;
			overflow: hidden !important;
		}
		body[data-route^="flow-chat"] #flow-chat-root,
		body[data-route^="flow-chat"] #flow-root {
			position: fixed !important;
			inset: 0 !important;
			z-index: 1020;
			width: 100vw !important;
			height: 100vh !important;
			height: 100dvh !important;
			overflow: hidden !important;
		}
	`;
	document.head.appendChild(style);
}
