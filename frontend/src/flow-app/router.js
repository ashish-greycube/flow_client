import { createRouter, createMemoryHistory } from "vue-router";
import ChatView from "./views/ChatView.vue";
import AgentsView from "./views/AgentsView.vue";

// Memory history, not the browser URL: this app is mounted inside one single
// Frappe Page ("flow-chat" — see flow/flow/page/flow_chat), and Frappe's own
// router already owns the real address bar for /app/*. Routing in-memory
// keeps the two from fighting each other; switching views here never touches
// the URL, so it can't confuse Frappe's own navigation or page caching.
//
// Flow Guide is deliberately not a route here — it's its own standalone
// desk page (flow/flow/page/flow_guide), reached via frappe.set_route
// ("flow-guide") from the header button instead.
export const router = createRouter({
	history: createMemoryHistory(),
	routes: [
		{ path: "/", name: "chat", component: ChatView },
		{ path: "/agents", name: "agents", component: AgentsView },
	],
});
