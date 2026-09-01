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

	// The navbar/page-head chrome above this div varies (title length, whether
	// the breadcrumb wraps, …), so a fixed `100vh - <guessed offsets>` formula
	// either leaves a gap or clips content depending on the page. Measuring the
	// div's own top and sizing it to reach the actual bottom of the viewport
	// is exact regardless of what's above it.
	function sizeRoot() {
		const top = root[0].getBoundingClientRect().top;
		root.css("height", `${Math.max(320, window.innerHeight - top)}px`);
	}
	sizeRoot();
	$(window).on("resize", sizeRoot);

	frappe.require(
		["/assets/flow/flow_chat/flow_chat.css", "/assets/flow/flow_chat/flow_chat.js"],
		() => {
			if (window.mountFlowChat) window.mountFlowChat(root.attr("id"));
			// The page head/breadcrumb can still settle its final height after this
			// point (e.g. once make_app_page finishes its own layout pass), which
			// shifts `top` out from under the very first measurement above. One
			// more pass next frame, once that's done, keeps the container from
			// coming out a touch too tall and clipping the composer.
			requestAnimationFrame(sizeRoot);
		}
	);
};

function ensureImmersiveStyle() {
	if (document.getElementById("flow-chat-immersive-style")) return;

	const style = document.createElement("style");
	style.id = "flow-chat-immersive-style";
	style.textContent = `
		body[data-route^="flow-chat"] header.navbar,
		body[data-route^="flow-chat"] .navbar,
		body[data-route^="flow-chat"] .page-head,
		body[data-route^="flow-chat"] .body-sidebar-container {
			display: none !important;
		}
		body[data-route^="flow-chat"] .main-section {
			padding-top: 0 !important;
		}
		body[data-route^="flow-chat"] .page-body {
			margin-top: 0 !important;
		}
	`;
	document.head.appendChild(style);
}
