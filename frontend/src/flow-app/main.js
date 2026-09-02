import { createApp } from "vue";
import Shell from "./Shell.vue";
import { router, attachFrappeRouteSync } from "./router";
import "@/index.css";
import "./theme.css";

// The consolidated Flow app: one Vue app, one router, one persistent Sidebar
// (Shell.vue) with Chat/Agents/Flow Guide swapping underneath it as routed
// views — replaces the earlier setup where Agents was a wholly separate
// Frappe Page + bundle with no sidebar of its own. Built as a separate bundle
// from the slide-in widget (see ../main.js) and loaded on demand by the
// "flow-chat" desk page. Mounted into #flow-root so it picks up the widget's
// existing CSS scope (postcss.config.js prefixes every rule to that id)
// without any build changes; the two bundles never load on the same page.
function mount(elementId) {
	const root = document.getElementById(elementId);
	if (!root) return;
	root.id = "flow-root";

	const apply = () => {
		const theme = document.documentElement.getAttribute("data-theme") || "light";
		root.setAttribute("data-theme", theme);
	};
	apply();
	new MutationObserver(apply).observe(document.documentElement, {
		attributes: true,
		attributeFilter: ["data-theme"],
	});

	createApp(Shell).use(router).mount(root);
	attachFrappeRouteSync();
}

window.mountFlowChat = mount;
