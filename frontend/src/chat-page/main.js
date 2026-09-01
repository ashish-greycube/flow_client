import { createApp } from "vue";
import ChatPage from "./ChatPage.vue";
import "@/index.css";
import "./theme.css";

// Full-page Flow Chat UI, built as a separate bundle from the slide-in panel
// (see ../main.js) and loaded on demand by the "flow-chat" desk page. Reuses
// the exact same store/api/components as the panel — only the shell around
// them differs. Mounted into #flow-root so it picks up the panel's existing
// CSS scope (postcss.config.js prefixes every rule to that id) without any
// build changes; the two bundles never load on the same page.
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

	createApp(ChatPage).mount(root);
}

window.mountFlowChat = mount;
