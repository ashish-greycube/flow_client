<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import SearchInput from "@/components/SearchInput.vue";
import { Button, FeatherIcon, Spinner, Badge } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadAllKnowledgeBases } from "@/api/client";

// Card grid (mirrors AgentsView.vue's card shape), single list — no
// Featured/Enabled/Disabled tabs, just every knowledge base with search.
const router = useRouter();

const loading = ref(true);
const knowledgeBases = ref([]);
const query = ref("");

onMounted(async () => {
	// A fresh fetch every time this view mounts, including on returning here
	// from Edit/New (a route change unmounts and remounts it), so the list is
	// never stale after a save.
	try {
		knowledgeBases.value = await loadAllKnowledgeBases();
	} finally {
		loading.value = false;
	}
});

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return knowledgeBases.value;
	return knowledgeBases.value.filter(
		(k) =>
			(k.title || "").toLowerCase().includes(q) || (k.description || "").toLowerCase().includes(q)
	);
});

function initials(title) {
	const words = (title || "?")
		.trim()
		.split(/\s+/)
		.filter((w) => /[a-z0-9]/i.test(w));
	return (words[0]?.[0] || "") + (words[1]?.[0] || "");
}

function description(text) {
	const flat = (text || "").replace(/\s+/g, " ").trim();
	if (!flat) return __("No description set.");
	return flat.length > 180 ? `${flat.slice(0, 180)}…` : flat;
}

function openKnowledgeBase(name) {
	router.push({ name: "knowledge-base-edit", params: { name } });
}

function newKnowledgeBase() {
	router.push({ name: "knowledge-base-new" });
}
</script>

<template>
	<div class="relative flex min-w-0 flex-1 flex-col bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<h1 class="text-lg font-normal text-ink-gray-9">{{ __("Knowledge Base") }}</h1>
			<Button variant="solid" @click="newKnowledgeBase">
				<template #prefix><FeatherIcon name="plus" class="h-3.5 w-3.5" /></template>
				{{ __("New Knowledge Base") }}
			</Button>
		</header>

		<div class="px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search knowledge bases…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div class="flow-scrollbar flex-1 overflow-y-auto px-6 pb-8">
			<div v-if="loading" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>

			<div v-else-if="!filtered.length" class="py-16 text-center text-sm text-ink-gray-5">
				{{ query.trim() ? __("No matching knowledge bases.") : __("No knowledge bases yet.") }}
			</div>

			<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
				<button
					v-for="k in filtered"
					:key="k.name"
					class="flex flex-col gap-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4 text-left hover:border-outline-gray-3 hover:shadow-sm"
					@click="openKnowledgeBase(k.name)"
				>
					<div class="flex items-start gap-3">
						<span
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2 text-xs font-normal text-ink-gray-7"
							>{{ initials(k.title) }}</span
						>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-semibold text-ink-gray-9">{{ k.title }}</div>
						</div>
					</div>

					<p class="line-clamp-2 text-sm font-normal leading-tight text-ink-gray-6">
						{{ description(k.description) }}
					</p>

					<div class="mt-auto flex items-center gap-1.5">
						<Badge
							variant="subtle"
							:theme="k.enabled ? 'green' : 'gray'"
							:label="k.enabled ? __('Enabled') : __('Disabled')"
						/>
						<Badge v-if="k.is_system_generated" variant="subtle" theme="gray" :label="__('Featured')" />
					</div>
				</button>
			</div>
		</div>
	</div>
</template>
