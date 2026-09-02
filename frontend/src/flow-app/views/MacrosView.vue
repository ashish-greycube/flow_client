<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import SearchInput from "@/components/SearchInput.vue";
import ViewHeader from "../components/ViewHeader.vue";
import { Badge, Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadMacros, runMacro } from "@/api/macros";

const router = useRouter();
const loading = ref(true);
const running = ref("");
const query = ref("");
const macros = ref([]);

const filtered = computed(() => {
	const value = query.value.trim().toLowerCase();
	if (!value) return macros.value;
	return macros.value.filter((macro) =>
		[macro.macro_name, macro.description, macro.agent].some((field) =>
			(field || "").toLowerCase().includes(value),
		),
	);
});

onMounted(refresh);

async function refresh() {
	loading.value = true;
	try {
		macros.value = await loadMacros();
	} catch (error) {
		showError(error, __("Could not load macros."));
	} finally {
		loading.value = false;
	}
}

async function run(macro) {
	running.value = macro.name;
	try {
		const result = await runMacro(macro.name);
		router.push({ name: "macro-run", params: { name: result.macro_run } });
	} catch (error) {
		showError(error, __("Could not run macro."));
	} finally {
		running.value = "";
	}
}

function showError(error, fallback) {
	frappe.show_alert({ message: error?.message || fallback, indicator: "red" });
}

function timeAgo(value) {
	return value && window.moment ? moment(value).fromNow() : value || "";
}

function canRun(macro) {
	return macro.owner === frappe.session.user || frappe.session.user === "Administrator";
}
</script>

<template>
	<main class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white">
		<ViewHeader :title="__('Macros')">
			<Button variant="solid" @click="router.push({ name: 'macro-new' })">
				<template #prefix><FeatherIcon name="plus" class="h-3.5 w-3.5" /></template>
				{{ __("New Macro") }}
			</Button>
		</ViewHeader>

		<div class="border-b border-outline-gray-1 px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search macros…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div class="flow-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-5">
			<div v-if="loading" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>
			<div v-else-if="!filtered.length" class="flex flex-col items-center py-16 text-center">
				<FeatherIcon name="layers" class="mb-3 h-8 w-8 text-ink-gray-4" />
				<p class="font-normal text-ink-gray-8">{{ __("No macros found") }}</p>
				<p class="mt-1 text-sm font-normal text-ink-gray-5">
					{{
						query
							? __("Try a different search.")
							: __("Create a macro to reuse a workflow.")
					}}
				</p>
			</div>
			<div v-else class="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
				<article
					v-for="macro in filtered"
					:key="macro.name"
					class="group flex min-h-36 cursor-pointer flex-col rounded-xl border border-outline-gray-1 bg-surface-white p-4 transition hover:border-outline-gray-2 hover:shadow-sm"
					@click="router.push({ name: 'macro', params: { name: macro.name } })"
				>
					<div class="flex items-start gap-3">
						<span
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2"
						>
							<FeatherIcon name="layers" class="h-4 w-4 text-ink-gray-6" />
						</span>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<p class="truncate text-sm font-normal text-ink-gray-9">
									{{ macro.macro_name }}
								</p>
								<Badge :theme="macro.enabled ? 'green' : 'gray'" variant="subtle">
									{{ macro.enabled ? __("Enabled") : __("Disabled") }}
								</Badge>
							</div>
							<p class="mt-1 line-clamp-2 text-sm font-normal text-ink-gray-5">
								{{ macro.description || __("No description") }}
							</p>
						</div>
						<Button
							variant="ghost"
							icon="play"
							:loading="running === macro.name"
							:disabled="!macro.enabled || !canRun(macro) || !!running"
							@click.stop="run(macro)"
						/>
					</div>
					<div
						class="mt-auto flex items-center justify-between border-t border-outline-gray-1 pt-3"
					>
						<p class="truncate text-xs font-normal text-ink-gray-6">
							{{ macro.agent }}
						</p>
						<p class="shrink-0 text-xs font-normal text-ink-gray-5">
							{{ timeAgo(macro.modified) }}
						</p>
					</div>
				</article>
			</div>
		</div>
	</main>
</template>
