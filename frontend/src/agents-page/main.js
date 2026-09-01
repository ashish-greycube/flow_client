import { createApp } from "vue";
import AgentsPage from "./AgentsPage.vue";
import "@/index.css";

// The Agents catalog page, opened from the Flow Chat sidebar's "Agent" link
// instead of the plain Flow Agent list view. Mounted into #flow-root so it
// picks up the same scoped styling as the chat page and the widget (see
// postcss.config.js) — the three bundles never load on the same page.
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

	createApp(AgentsPage).mount(root);
}

window.mountFlowAgents = mount;
