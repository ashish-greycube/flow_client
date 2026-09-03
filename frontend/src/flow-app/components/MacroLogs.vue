<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import DocSection from "@/components/DocSection.vue";
import { Badge, Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadMacroRuns } from "@/api/macros";

// Mirrors TriggerLogs.vue's shape (same expandable-row DocSection), adapted
// to Flow Macro Run's own fields — it tracks step progress and errors, not
// input/output text like Flow Run does.
const props = defineProps({ macro: { type: String, required: true } });
const router = useRouter();
const runs = ref([]);
const loading = ref(true);

onMounted(refresh);

async function refresh() {
	loading.value = true;
	try {
		runs.value = await loadMacroRuns(props.macro);
	} catch (error) {
		frappe.show_alert({
			message: error?.message || __("Could not load macro logs."),
			indicator: "red",
		});
	} finally {
		loading.value = false;
	}
}

function statusTheme(status) {
	return (
		{
			Completed: "green",
			Failed: "red",
			Running: "blue",
			Paused: "orange",
		}[status] || "gray"
	);
}

function runLabel(run) {
	return run.trigger === "Scheduled" ? __("Scheduled run") : __("Manual run");
}

function summary(run) {
	if (run.error) return String(run.error).replace(/\s+/g, " ").trim();
	return __("{0} of {1} steps", [run.current_step || 0, run.total_steps || 0]);
}

function timeAgo(value) {
	return value && window.moment ? moment(value).fromNow() : value || "";
}

function formatDate(value) {
	return value && window.moment ? moment(value).format("lll") : value || "—";
}

function openSession(session) {
	if (session) router.push({ name: "chat-session", params: { session } });
}

function openRun(name) {
	router.push({ name: "macro-run", params: { name } });
}
</script>

<template>
	<DocSection :label="__('Macro logs')" :collapsible="false">
		<template #header-suffix>
			<Button
				icon="refresh-cw"
				variant="ghost"
				:loading="loading"
				:aria-label="__('Refresh macro logs')"
				@click.stop="refresh"
			/>
		</template>

		<div v-if="loading && !runs.length" class="flex justify-center py-8">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>
		<div
			v-else-if="!runs.length"
			class="rounded-lg border border-dashed border-outline-gray-2 px-4 py-8 text-center"
		>
			<FeatherIcon name="activity" class="mx-auto h-6 w-6 text-ink-gray-4" />
			<p class="mt-2 text-sm text-ink-gray-7">{{ __("No macro runs yet") }}</p>
			<p class="mt-1 text-xs text-ink-gray-5">
				{{ __("Executions will appear here after this macro runs.") }}
			</p>
		</div>
		<div
			v-else
			class="overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white"
		>
			<details
				v-for="run in runs"
				:key="run.name"
				class="group border-t border-outline-gray-1 first:border-t-0"
			>
				<summary
					class="flex cursor-pointer list-none items-center gap-3 px-4 py-3 hover:bg-surface-gray-1"
				>
					<Badge :theme="statusTheme(run.status)" variant="subtle" :label="run.status" />
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium text-ink-gray-8">
							{{ runLabel(run) }}
						</p>
						<p class="mt-0.5 truncate text-xs text-ink-gray-5">
							{{ summary(run) }}
						</p>
					</div>
					<span class="shrink-0 text-xs text-ink-gray-5">{{
						timeAgo(run.started_at || run.creation)
					}}</span>
					<FeatherIcon
						name="chevron-right"
						class="h-4 w-4 shrink-0 text-ink-gray-5 transition-transform group-open:rotate-90"
					/>
				</summary>

				<div class="border-t border-outline-gray-1 bg-surface-gray-1 px-4 py-4">
					<dl class="grid gap-3 sm:grid-cols-3">
						<div>
							<dt class="text-xs text-ink-gray-5">{{ __("Run ID") }}</dt>
							<dd class="mt-1 truncate text-xs text-ink-gray-8" :title="run.name">
								{{ run.name }}
							</dd>
						</div>
						<div>
							<dt class="text-xs text-ink-gray-5">{{ __("Started") }}</dt>
							<dd class="mt-1 text-xs text-ink-gray-8">
								{{ formatDate(run.started_at) }}
							</dd>
						</div>
						<div>
							<dt class="text-xs text-ink-gray-5">{{ __("Steps") }}</dt>
							<dd class="mt-1 text-xs text-ink-gray-8">
								{{ run.current_step || 0 }} / {{ run.total_steps || 0 }}
							</dd>
						</div>
					</dl>

					<div v-if="run.error" class="mt-4">
						<p class="text-xs font-medium text-ink-red-4">{{ __("Error") }}</p>
						<pre class="macro-log-content text-ink-red-4">{{ run.error }}</pre>
					</div>

					<div class="mt-4 flex flex-wrap gap-2">
						<Button variant="subtle" @click="openRun(run.name)">
							<template #prefix>
								<FeatherIcon name="activity" class="h-3.5 w-3.5" />
							</template>
							{{ __("View run") }}
						</Button>
						<Button v-if="run.session" variant="subtle" @click="openSession(run.session)">
							<template #prefix>
								<FeatherIcon name="message-circle" class="h-3.5 w-3.5" />
							</template>
							{{ __("Open session") }}
						</Button>
					</div>
				</div>
			</details>
		</div>
	</DocSection>
</template>

<style scoped>
.macro-log-content {
	@apply mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-outline-gray-1 bg-surface-white p-3 text-xs leading-relaxed text-ink-gray-7;
}
</style>
