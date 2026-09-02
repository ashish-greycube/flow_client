<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import BrandMark from "@/components/BrandMark.vue";
import SearchInput from "@/components/SearchInput.vue";
import { FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";
import { searchSessions } from "@/api/client";

const router = useRouter();
const route = useRoute();
const { recentSessions, sessionName, sending, refreshHistory } = useStore();

const SIDEBAR_STORAGE_KEY = "flow-sidebar-collapsed";
const query = ref("");
const results = ref([]);
const searching = ref(false);
const collapsed = ref(readCollapsed());

let debounce;
let searchSeq = 0;

onMounted(() => refreshHistory().catch(() => {}));

watch(query, (q) => {
	clearTimeout(debounce);
	q = q.trim();
	const seq = ++searchSeq; // ignore responses from superseded queries
	if (!q) {
		results.value = [];
		searching.value = false;
		return;
	}
	searching.value = true;
	debounce = setTimeout(async () => {
		try {
			const found = await searchSessions(q);
			if (seq === searchSeq) results.value = found;
		} finally {
			if (seq === searchSeq) searching.value = false;
		}
	}, 250);
});

// Server results while searching, otherwise the recent list the store keeps fresh.
const list = computed(() => (query.value.trim() ? results.value : recentSessions.value));

// Routing (not a direct switchSession/newChat call) so the URL reflects which
// chat is open — ChatView's own route watcher does the actual store update in
// response, the same "route drives data" pattern the Agent/Knowledge Base
// pages use.
function startNewChat() {
	if (sending.value) return;
	router.push({ name: "chat" });
}

function choose(name) {
	if (sending.value) return;
	router.push({ name: "chat-session", params: { session: name } });
}

function openAgents() {
	router.push("/agents");
}

function openMacros() {
	router.push("/macros");
}

function openKnowledgeBases() {
	router.push("/knowledge-bases");
}

function openTriggers() {
	router.push("/triggers");
}

function toggleSidebar() {
	collapsed.value = !collapsed.value;
	try {
		localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed.value ? "1" : "0");
	} catch {
		// The preference is optional when browser storage is unavailable.
	}
}

// Nav rows to the doctypes a Flow user manages directly — same list views the
// desk already has, just one click away from the chat instead of hunting
// through the workspace.
function openList(doctype) {
	frappe.set_route("List", doctype);
}

function timeAgo(ds) {
	if (!ds) return "";
	return window.moment ? moment(ds).fromNow() : ds;
}

// Expanded by default — only actually collapsed once the user chooses to.
function readCollapsed() {
	try {
		return localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
	} catch {
		return false;
	}
}
</script>

<template>
	<aside
		class="flow-sidebar flex h-full shrink-0 flex-col overflow-hidden border-r border-outline-gray-1 bg-surface-gray-1 transition-[width] duration-300 ease-in-out"
		:class="collapsed ? 'w-12' : 'w-64'"
	>
		<div
			class="flex h-12 shrink-0 items-center gap-2"
			:class="collapsed ? 'justify-center px-2' : 'px-3'"
		>
			<BrandMark :size="20" />
			<span v-if="!collapsed" class="text-sm font-semibold text-ink-gray-9">{{
				__("Flow")
			}}</span>
		</div>

		<!-- action links: New Chat / Search Chat -->
		<nav class="flex flex-col gap-px px-2 pb-1.5">
			<button
				class="flex h-[30px] w-full items-center rounded text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="collapsed ? 'justify-center px-1' : 'gap-2 px-2'"
				:disabled="sending"
				:title="collapsed ? __('New Chat') : undefined"
				:aria-label="__('New Chat')"
				@click="startNewChat"
			>
				<FeatherIcon name="plus" class="h-4 w-4 shrink-0" />
				<span v-if="!collapsed">{{ __("New Chat") }}</span>
			</button>
		</nav>

		<!-- nav links: the doctypes a Flow user configures directly -->
		<nav class="flex flex-col gap-px border-t border-outline-gray-1 px-2 py-1.5">
			<button
				class="flex h-[30px] w-full items-center rounded text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="[
					collapsed ? 'justify-center px-1' : 'gap-2 px-2',
					route.path.startsWith('/agent') ? 'bg-surface-selected shadow-sm' : '',
				]"
				:title="collapsed ? __('Agent') : undefined"
				:aria-label="__('Agent')"
				@click="openAgents"
			>
				<FeatherIcon name="cpu" class="h-4 w-4 shrink-0" />
				<span v-if="!collapsed">{{ __("Agent") }}</span>
			</button>
			<button
				class="flex h-[30px] w-full items-center rounded text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="[
					collapsed ? 'justify-center px-1' : 'gap-2 px-2',
					route.path.startsWith('/macro') ? 'bg-surface-selected shadow-sm' : '',
				]"
				:title="collapsed ? __('Macro') : undefined"
				:aria-label="__('Macro')"
				@click="openMacros"
			>
				<FeatherIcon name="layers" class="h-4 w-4 shrink-0" />
				<span v-if="!collapsed">{{ __("Macro") }}</span>
			</button>
			<button
				class="flex h-[30px] w-full items-center rounded text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="[
					collapsed ? 'justify-center px-1' : 'gap-2 px-2',
					route.path.startsWith('/knowledge-bases') ? 'bg-surface-selected shadow-sm' : '',
				]"
				:title="collapsed ? __('Knowledge Base') : undefined"
				:aria-label="__('Knowledge Base')"
				@click="openKnowledgeBases"
			>
				<FeatherIcon name="book-open" class="h-4 w-4 shrink-0" />
				<span v-if="!collapsed">{{ __("Knowledge Base") }}</span>
			</button>
			<button
				class="flex h-[30px] w-full items-center rounded text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="[
					collapsed ? 'justify-center px-1' : 'gap-2 px-2',
					route.path.startsWith('/trigger') ? 'bg-surface-selected shadow-sm' : '',
				]"
				:title="collapsed ? __('Triggers') : undefined"
				:aria-label="__('Triggers')"
				@click="openTriggers"
			>
				<FeatherIcon name="zap" class="h-4 w-4 shrink-0" />
				<span v-if="!collapsed">{{ __("Triggers") }}</span>
			</button>
		</nav>

		<SearchInput v-if="!collapsed" v-model="query" :placeholder="__('Search chats…')" />

		<div v-if="!collapsed" class="flow-scrollbar flex-1 overflow-y-auto p-1.5">
			<p class="px-2 py-1.5 text-sm text-ink-gray-5">
				{{ query.trim() ? __("Results") : __("Recent chats") }}
			</p>

			<button
				v-for="s in list"
				:key="s.name"
				class="flex h-[30px] w-full items-center gap-2 rounded px-2 text-left hover:bg-surface-gray-2"
				:class="s.name === sessionName ? 'bg-surface-selected shadow-sm' : ''"
				@click="choose(s.name)"
			>
				<span class="flex-1 truncate text-sm text-ink-gray-8">{{
					s.title || s.name
				}}</span>
				<span class="shrink-0 text-[11px] text-ink-gray-5">{{ timeAgo(s.modified) }}</span>
			</button>

			<div v-if="searching" class="px-2 py-4 text-center text-xs text-ink-gray-5">
				{{ __("Searching…") }}
			</div>
			<div v-else-if="!list.length" class="px-2 py-4 text-center text-xs text-ink-gray-5">
				{{ query.trim() ? __("No matching chats") : __("No recent chats") }}
			</div>
		</div>
		<div v-else class="flex-1"></div>

		<div class="shrink-0 p-2">
			<button
				type="button"
				class="flex h-8 w-full items-center rounded-md text-ink-gray-7 hover:bg-surface-gray-2 hover:text-ink-gray-9"
				:class="collapsed ? 'justify-center px-1' : 'gap-2 px-2'"
				:title="collapsed ? __('Expand sidebar') : undefined"
				:aria-label="collapsed ? __('Expand sidebar') : __('Collapse sidebar')"
				:aria-expanded="!collapsed"
				@click="toggleSidebar"
			>
				<FeatherIcon
					name="chevrons-left"
					class="h-4 w-4 shrink-0 transition-transform duration-300"
					:class="collapsed ? 'rotate-180' : ''"
				/>
				<span v-if="!collapsed">{{ __("Collapse sidebar") }}</span>
			</button>
			<a
				v-if="!collapsed"
				class="mt-2 flex items-center justify-center border-t border-outline-gray-1 pt-2"
				href="https://greycube.in/"
				target="_blank"
				rel="noopener noreferrer"
			>
				<img
					:src="'/assets/flow/images/Greycube_Technologies.png'"
					:alt="__('GreyCube Technologies')"
					class="h-12 w-auto"
				/>
			</a>
		</div>
	</aside>
</template>
