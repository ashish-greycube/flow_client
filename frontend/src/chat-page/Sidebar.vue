<script setup>
import { ref, computed, watch } from "vue";
import BrandMark from "@/components/BrandMark.vue";
import SearchInput from "@/components/SearchInput.vue";
import { Button, FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";
import { searchSessions } from "@/api/client";

const { recentSessions, sessionName, switchSession, newChat, sending } = useStore();

const query = ref("");
const results = ref([]);
const searching = ref(false);

let debounce;
let searchSeq = 0;
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

function choose(name) {
	if (sending.value) return;
	switchSession(name);
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

		<div class="px-2 pb-2">
			<Button
				variant="ghost"
				class="h-[30px] w-full !justify-start text-sm"
				:disabled="sending"
				@click="newChat"
			>
				<template #prefix><FeatherIcon name="plus" class="h-3.5 w-3.5" /></template>
				{{ __("New chat") }}
			</Button>
		</div>

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
				<span class="flex-1 truncate text-sm text-ink-gray-8">{{ s.title || s.name }}</span>
				<span class="shrink-0 text-[11px] text-ink-gray-5">{{ timeAgo(s.modified) }}</span>
			</button>

			<div v-if="searching" class="px-2 py-4 text-center text-xs text-ink-gray-5">
				{{ __("Searching…") }}
			</div>
			<div v-else-if="!list.length" class="px-2 py-4 text-center text-xs text-ink-gray-5">
				{{ query.trim() ? __("No matching chats") : __("No recent chats") }}
			</div>
		</div>
	</aside>
</template>
