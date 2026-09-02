import { createRouter, createMemoryHistory } from "vue-router";
import ChatView from "./views/ChatView.vue";
import AgentsView from "./views/AgentsView.vue";
import AgentFormView from "./views/AgentFormView.vue";
import MacrosView from "./views/MacrosView.vue";
import MacroView from "./views/MacroView.vue";
import MacroRunView from "./views/MacroRunView.vue";
import TriggersView from "./views/TriggersView.vue";
import TriggerView from "./views/TriggerView.vue";
import KnowledgeBasesView from "./views/KnowledgeBasesView.vue";
import KnowledgeBaseFormView from "./views/KnowledgeBaseFormView.vue";
import KnowledgeSourceFormView from "./views/KnowledgeSourceFormView.vue";

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
		{ path: "/c/:session", name: "chat-session", component: ChatView, props: true },
		{ path: "/agents", name: "agents", component: AgentsView },
		{ path: "/agents/new", name: "agent-new", component: AgentFormView },
		{ path: "/agents/:name", name: "agent-edit", component: AgentFormView },
		{ path: "/macros", name: "macros", component: MacrosView },
		{ path: "/macros/new", name: "macro-new", component: MacroView, props: { isNew: true } },
		{ path: "/macros/:name", name: "macro", component: MacroView, props: true },
		{ path: "/macro-runs/:name", name: "macro-run", component: MacroRunView, props: true },
		{ path: "/triggers", name: "triggers", component: TriggersView },
		{
			path: "/triggers/new",
			name: "trigger-new",
			component: TriggerView,
			props: { isNew: true },
		},
		{ path: "/triggers/:name", name: "trigger", component: TriggerView, props: true },
		{ path: "/knowledge-bases", name: "knowledge-bases", component: KnowledgeBasesView },
		{
			path: "/knowledge-bases/new",
			name: "knowledge-base-new",
			component: KnowledgeBaseFormView,
		},
		{
			path: "/knowledge-bases/:name",
			name: "knowledge-base-edit",
			component: KnowledgeBaseFormView,
		},
		{
			path: "/knowledge-bases/:name/sources/new",
			name: "knowledge-source-new",
			component: KnowledgeSourceFormView,
		},
		{
			path: "/knowledge-bases/:name/sources/:source",
			name: "knowledge-source-edit",
			component: KnowledgeSourceFormView,
		},
	],
});

// vue-router location -> the extra segments Frappe's route should carry
// after "flow-chat" (frappe.set_route("flow-chat", ...segments)).
function toFrappeSegments(route) {
	if (route.name === "chat-session") return ["flow-chat", "c", route.params.session];
	if (route.name === "agents") return ["flow-chat", "agents"];
	if (route.name === "agent-new") return ["flow-chat", "agents", "new"];
	if (route.name === "agent-edit") return ["flow-chat", "agents", route.params.name];
	if (route.name === "macros") return ["flow-chat", "macros"];
	if (route.name === "macro-new") return ["flow-chat", "macros", "new"];
	if (route.name === "macro") return ["flow-chat", "macros", route.params.name];
	if (route.name === "macro-run") return ["flow-chat", "macro-runs", route.params.name];
	if (route.name === "triggers") return ["flow-chat", "triggers"];
	if (route.name === "trigger-new") return ["flow-chat", "triggers", "new"];
	if (route.name === "trigger") return ["flow-chat", "triggers", route.params.name];
	if (route.name === "knowledge-bases") return ["flow-chat", "knowledge-bases"];
	if (route.name === "knowledge-base-new") return ["flow-chat", "knowledge-bases", "new"];
	if (route.name === "knowledge-base-edit") {
		return ["flow-chat", "knowledge-bases", route.params.name];
	}
	if (route.name === "knowledge-source-new") {
		return ["flow-chat", "knowledge-bases", route.params.name, "sources", "new"];
	}
	if (route.name === "knowledge-source-edit") {
		return ["flow-chat", "knowledge-bases", route.params.name, "sources", route.params.source];
	}
	return ["flow-chat"];
}

// Frappe's current route segments -> a vue-router location to push.
function toVueLocation(segments) {
	const [, section, sub, sourcesWord, sourceSub] = segments;
	if (section === "c" && sub) return { name: "chat-session", params: { session: sub } };
	if (section === "agents") {
		if (!sub) return { name: "agents" };
		if (sub === "new") return { name: "agent-new" };
		return { name: "agent-edit", params: { name: sub } };
	}
	if (section === "macros") {
		if (!sub) return { name: "macros" };
		if (sub === "new") return { name: "macro-new" };
		return { name: "macro", params: { name: sub } };
	}
	if (section === "macro-runs" && sub) {
		return { name: "macro-run", params: { name: sub } };
	}
	if (section === "triggers") {
		if (!sub) return { name: "triggers" };
		if (sub === "new") return { name: "trigger-new" };
		return { name: "trigger", params: { name: sub } };
	}
	if (section === "knowledge-bases") {
		if (!sub) return { name: "knowledge-bases" };
		if (sub === "new") return { name: "knowledge-base-new" };
		if (sourcesWord === "sources") {
			if (sourceSub === "new") return { name: "knowledge-source-new", params: { name: sub } };
			if (sourceSub) {
				return { name: "knowledge-source-edit", params: { name: sub, source: sourceSub } };
			}
		}
		return { name: "knowledge-base-edit", params: { name: sub } };
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
		if (
			current.name === target.name &&
			current.params.name === target.params?.name &&
			current.params.session === target.params?.session
		) {
			return;
		}
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
