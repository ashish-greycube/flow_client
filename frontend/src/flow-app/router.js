import { createRouter, createMemoryHistory } from "vue-router";
import ChatView from "./views/ChatView.vue";
import AgentsView from "./views/AgentsView.vue";
import AgentFormView from "./views/AgentFormView.vue";
import MacrosView from "./views/MacrosView.vue";
import MacroView from "./views/MacroView.vue";
import MacroRunView from "./views/MacroRunView.vue";

// Frappe treats additional segments after a Page route as route arguments, so
// the embedded app can use clean, refresh-safe paths under /desk/flow-chat.
const routeBase =
	window.location.pathname.match(/^(.*?\/flow-chat)(?:\/|$)/)?.[1] || "/desk/flow-chat";

// Memory history, not the browser URL directly: this app is mounted inside
// one single Frappe Page ("flow-chat" — see flow/flow/page/flow_chat), and
// Frappe's own router already owns the real address bar for /app/*. Routing
// in-memory keeps vue-router's own navigation from fighting Frappe's, while
// attachFrappeRouteSync() below keeps the *visible* URL in sync by pushing
// extra segments onto the flow-chat route (e.g. /app/flow-chat/agents/foo)
// through frappe.set_route — so links are still real and bookmarkable/
// shareable, and the browser back/forward buttons and deep links still work,
// without vue-router ever touching history itself.
//
// Flow Guide is deliberately not a route here — it's its own standalone
// desk page (flow/flow/page/flow_guide), reached via frappe.set_route
// ("flow-guide") from the header button instead.
export const router = createRouter({
	history: createMemoryHistory(),
	routes: [
		{ path: "/", name: "chat", component: ChatView },
		{ path: "/agents", name: "agents", component: AgentsView },
		{ path: "/agents/new", name: "agent-new", component: AgentFormView },
		{ path: "/agents/:name", name: "agent-edit", component: AgentFormView },
		{ path: "/macros", name: "macros", component: MacrosView },
		{ path: "/macros/new", name: "macro-new", component: MacroView, props: { isNew: true } },
		{ path: "/macros/:name", name: "macro", component: MacroView, props: true },
		{ path: "/macro-runs/:name", name: "macro-run", component: MacroRunView, props: true },
	],
});

// vue-router location -> the extra segments Frappe's route should carry
// after "flow-chat" (frappe.set_route("flow-chat", ...segments)).
function toFrappeSegments(route) {
	if (route.name === "agents") return ["flow-chat", "agents"];
	if (route.name === "agent-new") return ["flow-chat", "agents", "new"];
	if (route.name === "agent-edit") return ["flow-chat", "agents", route.params.name];
	return ["flow-chat"];
}

// Frappe's current route segments -> a vue-router location to push.
function toVueLocation(segments) {
	const [, section, sub] = segments;
	if (section === "agents") {
		if (!sub) return { name: "agents" };
		if (sub === "new") return { name: "agent-new" };
		return { name: "agent-edit", params: { name: sub } };
	}
	return { name: "chat" };
}

function segmentsEqual(a, b) {
	return a.length === b.length && a.every((s, i) => s === b[i]);
}

// Re-entrancy guard: a push on either side triggers the other side's
// listener too, and without this they'd volley the same navigation back
// and forth forever. The flag has to stay set for the *entire* round trip —
// including whatever the other side's own listener does synchronously
// partway through resolving — so each branch awaits its navigation fully
// before clearing it. Frappe's own "change" event fires from inside
// `frappe.set_route()`'s async body before its promise resolves, and
// vue-router's afterEach hooks fire before `router.push()`'s promise
// resolves, so awaiting each all the way through is what makes the other
// side's re-entrant listener call see `syncing` still true and bail out.
let syncing = false;

router.afterEach(async (to) => {
	if (syncing) return;
	const target = toFrappeSegments(to);
	if (segmentsEqual(frappe.get_route() || [], target)) return;
	syncing = true;
	try {
		await frappe.set_route(...target);
	} finally {
		syncing = false;
	}
});

// Called once after mounting: mirrors Frappe route changes (browser back/
// forward, a pasted deep link, frappe.set_route calls elsewhere) into
// vue-router, and does one initial sync so a direct/deep load of
// /app/flow-chat/agents/<name> opens straight into that view.
export function attachFrappeRouteSync() {
	const sync = async () => {
		if (syncing) return;
		const segments = frappe.get_route() || [];
		if (segments[0] !== "flow-chat") return; // navigated off this page entirely
		const target = toVueLocation(segments);
		const current = router.currentRoute.value;
		if (current.name === target.name && current.params.name === target.params?.name) return;
		syncing = true;
		try {
			await router.push(target);
		} finally {
			syncing = false;
		}
	};
	sync();
	frappe.router.on("change", sync);
}
