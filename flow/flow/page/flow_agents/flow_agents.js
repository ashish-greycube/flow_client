frappe.pages["flow-agents"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Agents"),
		single_column: true,
	});

	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty().css({ padding: 0 });

	const root = $("<div>", { id: "flow-agents-root" }).appendTo($parent);

	frappe.require(
		["/assets/flow/flow_agents/flow_agents.css", "/assets/flow/flow_agents/flow_agents.js"],
		() => {
			if (window.mountFlowAgents) window.mountFlowAgents(root.attr("id"));
		}
	);
};
