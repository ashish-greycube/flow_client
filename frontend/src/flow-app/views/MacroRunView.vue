<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Badge, Breadcrumbs, Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadMacro, loadMacroRun, stopMacroRun } from "@/api/macros";

const props = defineProps({ name: { type: String, required: true } });
const router = useRouter();
const run = ref(null);
const macroTitle = ref("");
const loading = ref(true);
const stopping = ref(false);
let timer;

const active = computed(() => ["Queued", "Running", "Paused"].includes(run.value?.status));
const canStop = computed(
	() => run.value?.owner === frappe.session.user || frappe.session.user === "Administrator",
);
const progress = computed(() => {
	if (!run.value?.total_steps) return 0;
	return Math.min(100, Math.round((run.value.current_step / run.value.total_steps) * 100));
});
const statusTheme = computed(
	() =>
		({ Completed: "green", Failed: "red", Running: "blue", Paused: "orange" })[
			run.value?.status
		] || "gray",
);
const breadcrumbs = computed(() => {
	const items = [{ label: __("Macros"), route: { name: "macros" } }];
	if (run.value?.macro) {
		items.push({
			label: macroTitle.value || run.value.macro,
			route: { name: "macro", params: { name: run.value.macro } },
		});
	}
	items.push({
		label: __("Macro Run"),
		route: { name: "macro-run", params: { name: props.name } },
	});
	return items;
});

onMounted(refresh);
onUnmounted(() => clearTimeout(timer));

async function refresh() {
	clearTimeout(timer);
	try {
		run.value = await loadMacroRun(props.name);
		if (!macroTitle.value && run.value.macro) {
			const macro = await loadMacro(run.value.macro);
			macroTitle.value = macro.macro_name || macro.name;
		}
		if (active.value && run.value.status !== "Paused") timer = setTimeout(refresh, 3000);
	} catch (error) {
		frappe.show_alert({
			message: error?.message || __("Could not load macro run."),
			indicator: "red",
		});
	} finally {
		loading.value = false;
	}
}

async function stop() {
	stopping.value = true;
	try {
		await stopMacroRun(props.name);
		await refresh();
		frappe.show_alert({ message: __("Macro run stopped."), indicator: "green" });
	} catch (error) {
		frappe.show_alert({
			message: error?.message || __("Could not stop macro run."),
			indicator: "red",
		});
	} finally {
		stopping.value = false;
	}
}

function openSession() {
	if (!run.value?.session) return;
	router.push({ name: "chat-session", params: { session: run.value.session } });
}

function formatDate(value) {
	return value && window.moment ? moment(value).format("lll") : value || "—";
}
</script>

<template>
	<main
		class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9"
	>
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<Breadcrumbs :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<Button icon="refresh-cw" variant="ghost" :loading="loading" @click="refresh" />
				<Button
					v-if="active && canStop"
					theme="red"
					variant="subtle"
					:loading="stopping"
					@click="stop"
				>
					{{ __("Stop") }}
				</Button>
			</div>
		</header>

		<div v-if="loading && !run" class="flex min-h-0 flex-1 items-center justify-center">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>
		<div v-else-if="run" class="flow-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-6">
			<div class="mx-auto w-full max-w-3xl space-y-6">
				<div>
					<div class="flex items-center gap-3">
						<h1 class="min-w-0 truncate text-2xl font-semibold text-ink-gray-9">
							{{ __("Macro Run") }}
						</h1>
						<Badge :theme="statusTheme" variant="subtle">{{ run.status }}</Badge>
					</div>
					<p class="mt-1 text-xs font-normal text-ink-gray-5">{{ run.name }}</p>
				</div>
				<section class="rounded-xl border border-outline-gray-1 p-5">
					<div class="flex items-start justify-between gap-4">
						<div>
							<button
								class="text-left text-lg font-medium text-ink-gray-9 hover:underline"
								@click="
									router.push({ name: 'macro', params: { name: run.macro } })
								"
							>
								{{ macroTitle || run.macro }}
							</button>
						</div>
					</div>
					<div class="mt-5 h-2 overflow-hidden rounded-full bg-surface-gray-2">
						<div
							class="h-full rounded-full bg-blue-500 transition-all"
							:style="{ width: `${progress}%` }"
						></div>
					</div>
					<p class="mt-2 text-sm font-normal text-ink-gray-5">
						{{
							__("{0} of {1} steps completed", [
								run.current_step || 0,
								run.total_steps || 0,
							])
						}}
					</p>
				</section>

				<section class="rounded-xl border border-outline-gray-1 p-5">
					<h2 class="mb-4 text-sm font-medium text-ink-gray-9">
						{{ __("Run context") }}
					</h2>
					<dl class="grid gap-x-8 gap-y-4 md:grid-cols-2">
						<div>
							<dt class="text-xs font-normal text-ink-gray-5">{{ __("Agent") }}</dt>
							<dd class="mt-1 text-sm font-normal text-ink-gray-8">
								{{ run.agent || "—" }}
							</dd>
						</div>
						<div>
							<dt class="text-xs font-normal text-ink-gray-5">
								{{ __("Trigger") }}
							</dt>
							<dd class="mt-1 text-sm font-normal text-ink-gray-8">
								{{ run.trigger }}
							</dd>
						</div>
						<div>
							<dt class="text-xs font-normal text-ink-gray-5">
								{{ __("Started") }}
							</dt>
							<dd class="mt-1 text-sm font-normal text-ink-gray-8">
								{{ formatDate(run.started_at) }}
							</dd>
						</div>
						<div>
							<dt class="text-xs font-normal text-ink-gray-5">
								{{ __("Finished") }}
							</dt>
							<dd class="mt-1 text-sm font-normal text-ink-gray-8">
								{{ formatDate(run.finished_at) }}
							</dd>
						</div>
					</dl>
					<div class="mt-5 flex flex-wrap gap-2">
						<Button v-if="run.session" variant="subtle" @click="openSession">
							<template #prefix
								><FeatherIcon name="message-circle" class="h-3.5 w-3.5"
							/></template>
							{{ __("Open session") }}
						</Button>
					</div>
				</section>

				<section v-if="run.error" class="rounded-xl border border-red-200 bg-red-50 p-5">
					<h2 class="mb-2 text-sm font-medium text-red-700">{{ __("Error") }}</h2>
					<pre class="whitespace-pre-wrap text-sm font-normal text-red-700">{{
						run.error
					}}</pre>
				</section>
			</div>
		</div>
	</main>
</template>
