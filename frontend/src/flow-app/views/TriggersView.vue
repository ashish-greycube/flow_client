<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import SearchInput from "@/components/SearchInput.vue";
import { Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadTriggers } from "@/api/triggers";

const TABS = [
	{ key: "enabled", label: __("Enabled") },
	{ key: "disabled", label: __("Disabled") },
];

const router = useRouter();
const loading = ref(true);
const query = ref("");
const triggers = ref([]);
const activeTab = ref("enabled");

const tabbed = computed(() =>
	triggers.value.filter((trigger) =>
		activeTab.value === "enabled" ? trigger.enabled : !trigger.enabled,
	),
);

const filtered = computed(() => {
	const value = query.value.trim().toLowerCase();
	if (!value) return tabbed.value;
	return tabbed.value.filter((trigger) =>
		[
			trigger.title,
			trigger.agent,
			trigger.event,
			trigger.target_doctype,
			trigger.prompt_template,
		].some((field) => (field || "").toLowerCase().includes(value)),
	);
});

onMounted(refresh);

async function refresh() {
	loading.value = true;
	try {
		triggers.value = await loadTriggers();
	} catch (error) {
		showError(error, __("Could not load triggers."));
	} finally {
		loading.value = false;
	}
}

function tabCount(key) {
	return triggers.value.filter((trigger) =>
		key === "enabled" ? trigger.enabled : !trigger.enabled,
	).length;
}

function eventSummary(trigger) {
	if (trigger.event === "Scheduled") {
		return trigger.cron_expression || __("Schedule not set");
	}
	const event = (trigger.doc_event || "").replaceAll("_", " ");
	return [trigger.target_doctype, event].filter(Boolean).join(" · ") || __("Event not set");
}

function promptSummary(value) {
	const text = (value || "").replace(/\s+/g, " ").trim();
	return text || __("No prompt set");
}

function timeAgo(value) {
	return value && window.moment ? moment(value).fromNow() : value || "";
}

function showError(error, fallback) {
	frappe.show_alert({ message: error?.message || fallback, indicator: "red" });
}
</script>

<template>
	<main
		class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9"
	>
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<h1 class="text-lg font-normal text-ink-gray-9">{{ __("Triggers") }}</h1>
			<Button variant="solid" @click="router.push({ name: 'trigger-new' })">
				<template #prefix><FeatherIcon name="plus" class="h-3.5 w-3.5" /></template>
				{{ __("New Trigger") }}
			</Button>
		</header>

		<div class="flex items-center gap-1 border-b border-outline-gray-1 px-6">
			<button
				v-for="tab in TABS"
				:key="tab.key"
				class="relative flex items-center gap-1.5 px-1 py-3 text-sm"
				:class="
					activeTab === tab.key
						? 'text-ink-gray-9'
						: 'text-ink-gray-5 hover:text-ink-gray-8'
				"
				@click="activeTab = tab.key"
			>
				{{ tab.label }}
				<span class="rounded-full bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">
					{{ tabCount(tab.key) }}
				</span>
				<span
					v-if="activeTab === tab.key"
					class="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-ink-gray-9"
				></span>
			</button>
		</div>

		<div class="px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search triggers…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div class="flow-scrollbar min-h-0 flex-1 overflow-y-auto px-6 pb-8">
			<div v-if="loading" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>
			<div v-else-if="!filtered.length" class="flex flex-col items-center py-16 text-center">
				<FeatherIcon name="zap" class="mb-3 h-8 w-8 text-ink-gray-4" />
				<p class="font-normal text-ink-gray-8">{{ __("No triggers found") }}</p>
				<p class="mt-1 text-sm font-normal text-ink-gray-5">
					{{
						query.trim()
							? __("Try a different search.")
							: activeTab === "enabled"
								? __("Create or enable a trigger to automate an agent.")
								: __("No triggers are disabled.")
					}}
				</p>
			</div>
			<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
				<article
					v-for="trigger in filtered"
					:key="trigger.name"
					class="group flex min-h-40 cursor-pointer flex-col gap-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4 text-left transition hover:border-outline-gray-3 hover:shadow-sm"
					@click="router.push({ name: 'trigger', params: { name: trigger.name } })"
				>
					<div class="flex items-start gap-3">
						<span
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2"
						>
							<FeatherIcon name="zap" class="h-4 w-4 text-ink-gray-6" />
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-semibold text-ink-gray-9">
								{{ trigger.title }}
							</p>
							<p class="truncate text-xs font-normal text-ink-gray-5">
								{{ trigger.agent }}
							</p>
						</div>
						<span
							class="rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-6"
						>
							{{ trigger.event }}
						</span>
					</div>

					<div>
						<p class="truncate text-xs font-medium capitalize text-ink-gray-7">
							{{ eventSummary(trigger) }}
						</p>
						<p
							class="mt-1 line-clamp-2 text-sm font-normal leading-tight text-ink-gray-6"
						>
							{{ promptSummary(trigger.prompt_template) }}
						</p>
					</div>

					<div
						class="mt-auto flex items-center justify-between gap-2 border-t border-outline-gray-1 pt-3"
					>
						<span
							class="rounded-full px-2 py-0.5 text-xs"
							:class="
								trigger.enabled
									? 'bg-surface-green-2 text-ink-green-2'
									: 'bg-surface-gray-2 text-ink-gray-6'
							"
						>
							{{ trigger.enabled ? __("Enabled") : __("Disabled") }}
						</span>
						<p class="shrink-0 text-xs font-normal text-ink-gray-5">
							{{ timeAgo(trigger.modified) }}
						</p>
					</div>
				</article>
			</div>
		</div>
	</main>
</template>
