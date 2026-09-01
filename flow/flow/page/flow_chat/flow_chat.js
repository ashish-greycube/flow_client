frappe.pages["flow-chat"].on_page_load = function (wrapper) {
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
