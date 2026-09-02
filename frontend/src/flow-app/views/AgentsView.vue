<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import SearchInput from "@/components/SearchInput.vue";
import { Button, FeatherIcon, Spinner, Badge } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadAllAgents } from "@/api/client";

const router = useRouter();

// Flow has no marketplace/catalog concept (installs, versions, publishers)
// like Jarvis's Agents page does — these tabs map onto what a Flow Agent
// actually has: "Featured" is every agent regardless of enabled/disabled/
// system-generated, the other two filter by its `enabled` flag.
const TABS = [
	{ key: "featured", label: __("Featured") },
	{ key: "enabled", label: __("Enabled") },
	{ key: "disabled", label: __("Disabled") },
];

const loading = ref(true);
const agents = ref([]);
const activeTab = ref("featured");
const query = ref("");

onMounted(async () => {
	// A fresh fetch every time this view mounts, including on returning here
	// from Edit/New (a route change unmounts and remounts it), so the list is
	// never stale after a save/delete.
	try {
		agents.value = await loadAllAgents();
	} finally {
		loading.value = false;
	}
});

const tabbed = computed(() => {
	if (activeTab.value === "featured") return agents.value;
	if (activeTab.value === "enabled") return agents.value.filter((a) => a.enabled);
	return agents.value.filter((a) => !a.enabled);
});

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return tabbed.value;
	return tabbed.value.filter(
		(a) =>
			(a.title || "").toLowerCase().includes(q) || (a.instructions || "").toLowerCase().includes(q)
	);
});

function tabCount(key) {
	if (key === "featured") return agents.value.length;
	if (key === "enabled") return agents.value.filter((a) => a.enabled).length;
	return agents.value.filter((a) => !a.enabled).length;
}

// A short avatar chip from the title's initials — the closest stand-in for
// Jarvis's per-agent icon, without inventing an icon-upload field.
function initials(title) {
	// Skip purely punctuation "words" ("&", "-", …) — a title like "AR &
	// Collections Operator" should read "AR", not "A&".
	const words = (title || "?")
		.trim()
		.split(/\s+/)
		.filter((w) => /[a-z0-9]/i.test(w));
	return (words[0]?.[0] || "") + (words[1]?.[0] || "");
}

function description(text) {
	const flat = (text || "").replace(/\s+/g, " ").trim();
	if (!flat) return __("No instructions set.");
	return flat.length > 180 ? `${flat.slice(0, 180)}…` : flat;
}

function openAgent(name) {
	router.push({ name: "agent-edit", params: { name } });
}

function newAgent() {
	router.push({ name: "agent-new" });
}
</script>

<template>
	<div class="relative flex min-w-0 flex-1 flex-col bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<h1 class="text-lg font-normal text-ink-gray-9">{{ __("Agents") }}</h1>
			<Button variant="solid" @click="newAgent">
				<template #prefix><FeatherIcon name="plus" class="h-3.5 w-3.5" /></template>
				{{ __("New Agent") }}
			</Button>
		</header>

		<div class="flex items-center gap-1 border-b border-outline-gray-1 px-6">
			<button
				v-for="tab in TABS"
				:key="tab.key"
				class="relative flex items-center gap-1.5 px-1 py-3 text-sm"
				:class="activeTab === tab.key ? 'text-ink-gray-9' : 'text-ink-gray-5 hover:text-ink-gray-8'"
				@click="activeTab = tab.key"
			>
				{{ tab.label }}
				<span class="rounded-full bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{
					tabCount(tab.key)
				}}</span>
				<span
					v-if="activeTab === tab.key"
					class="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-ink-gray-9"
				></span>
			</button>
		</div>

		<div class="px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search agents…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div class="flow-scrollbar flex-1 overflow-y-auto px-6 pb-8">
			<div v-if="loading" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>

			<div v-else-if="!filtered.length" class="py-16 text-center text-sm text-ink-gray-5">
				{{ query.trim() ? __("No matching agents.") : __("No agents in this tab yet.") }}
			</div>

			<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
				<button
					v-for="a in filtered"
					:key="a.name"
					class="flex flex-col gap-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4 text-left hover:border-outline-gray-3 hover:shadow-sm"
					@click="openAgent(a.name)"
				>
					<div class="flex items-start gap-3">
						<span
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2 text-xs font-normal text-ink-gray-7"
							>{{ initials(a.title) }}</span
						>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-semibold text-ink-gray-9">{{ a.title }}</div>
							<div class="truncate text-xs font-normal text-ink-gray-5">
								{{ a.model ? __("Model: {0}", [a.model]) : __("No model set") }}
							</div>
						</div>
					</div>

					<p class="line-clamp-2 text-sm font-normal leading-tight text-ink-gray-6">
					{{ description(a.instructions) }}
				</p>

					<div class="mt-auto flex items-center gap-1.5">
						<Badge
							variant="subtle"
							:theme="a.enabled ? 'green' : 'gray'"
							:label="a.enabled ? __('Enabled') : __('Disabled')"
						/>
						<Badge v-if="a.is_system_generated" variant="subtle" theme="gray" :label="__('Featured')" />
					</div>
				</button>
			</div>
		</div>
	</div>
</template>
