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
const { recentSessions, sessionName, switchSession, newChat, sending, refreshHistory } =
	useStore();

const query = ref("");
const results = ref([]);
const searching = ref(false);

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

// A chat action only means something on the Chat view — jump there first if
// the sidebar is clicked from Agents/Flow Guide.
function goToChat() {
	if (router.currentRoute.value.path !== "/") router.push("/");
}

function startNewChat() {
	newChat();
	goToChat();
}

function choose(name) {
	if (sending.value) return;
	switchSession(name);
	goToChat();
}

function openAgents() {
	router.push("/agents");
}

function openMacros() {
	router.push("/macros");
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
</script>

<template>
	<aside
		class="flow-sidebar flex h-full w-64 shrink-0 flex-col border-r border-outline-gray-1 bg-surface-gray-1"
	>
		<div class="flex items-center gap-2 px-3 py-3">
			<BrandMark :size="20" />
			<span class="text-sm font-semibold text-ink-gray-9">{{ __("Flow") }}</span>
		</div>

		<!-- action links: New Chat / Search Chat -->
		<nav class="flex flex-col gap-px px-2 pb-1.5">
			<button
				class="flex h-[30px] w-full items-center gap-2 rounded px-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:disabled="sending"
				@click="startNewChat"
			>
				<FeatherIcon name="plus" class="h-4 w-4 shrink-0" />
				{{ __("New Chat") }}
			</button>
		</nav>

		<!-- nav links: the doctypes a Flow user configures directly -->
		<nav class="flex flex-col gap-px border-t border-outline-gray-1 px-2 py-1.5">
			<button
				class="flex h-[30px] w-full items-center gap-2 rounded px-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="route.path === '/agents' ? 'bg-surface-selected shadow-sm' : ''"
				@click="openAgents"
			>
				<FeatherIcon name="cpu" class="h-4 w-4 shrink-0" />
				{{ __("Agent") }}
			</button>
			<button
				class="flex h-[30px] w-full items-center gap-2 rounded px-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				:class="route.path.startsWith('/macro') ? 'bg-surface-selected shadow-sm' : ''"
				@click="openMacros"
			>
				<FeatherIcon name="layers" class="h-4 w-4 shrink-0" />
				{{ __("Macro") }}
			</button>
			<button
				class="flex h-[30px] w-full items-center gap-2 rounded px-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				@click="openList('Flow Knowledge Base')"
			>
				<FeatherIcon name="book-open" class="h-4 w-4 shrink-0" />
				{{ __("Knowledge Base") }}
			</button>
			<button
				class="flex h-[30px] w-full items-center gap-2 rounded px-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
				@click="openList('Flow Trigger')"
			>
				<FeatherIcon name="zap" class="h-4 w-4 shrink-0" />
				{{ __("Triggers") }}
			</button>
		</nav>

		<SearchInput v-model="query" :placeholder="__('Search chats…')" />

		<div class="flow-scrollbar flex-1 overflow-y-auto p-1.5">
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

		<div class="flex shrink-0 items-center justify-center border-t border-outline-gray-1 px-3 py-4">
			<a href="https://greycube.in/" target="_blank" rel="noopener noreferrer">
				<img
					:src="'/assets/flow/images/Greycube_Technologies.png'"
					:alt="__('GreyCube Technologies')"
					class="h-[3.8rem] w-auto"
				/>
			</a>
		</div>
	</aside>
</template>
