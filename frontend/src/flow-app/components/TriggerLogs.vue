<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import DocSection from "@/components/DocSection.vue";
import { Badge, Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadTriggerRuns } from "@/api/triggers";

const props = defineProps({ trigger: { type: String, required: true } });
const router = useRouter();
const runs = ref([]);
const loading = ref(true);

onMounted(refresh);

async function refresh() {
	loading.value = true;
	try {
		runs.value = await loadTriggerRuns(props.trigger);
	} catch (error) {
		frappe.show_alert({
			message: error?.message || __("Could not load trigger logs."),
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

function referenceLabel(run) {
	return (
		[run.reference_doctype, run.reference_name].filter(Boolean).join(" · ") ||
		__("Scheduled run")
	);
}

function summary(run) {
	const value = run.error || run.output || run.input || __("No run details yet.");
	return String(value).replace(/\s+/g, " ").trim();
}

function timeAgo(value) {
	return value && window.moment ? moment(value).fromNow() : value || "";
}

function formatDate(value) {
	return value && window.moment ? moment(value).format("lll") : value || "—";
}

function openSession(session) {
	if (session) router.push({ name: "chat", query: { session } });
}
</script>

<template>
	<DocSection :label="__('Trigger logs')" :collapsible="false">
		<template #header-suffix>
			<Button
				icon="refresh-cw"
				variant="ghost"
				:loading="loading"
				:aria-label="__('Refresh trigger logs')"
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
			<p class="mt-2 text-sm text-ink-gray-7">{{ __("No trigger runs yet") }}</p>
			<p class="mt-1 text-xs text-ink-gray-5">
				{{ __("Executions will appear here after this trigger fires.") }}
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
							{{ referenceLabel(run) }}
						</p>
						<p class="mt-0.5 truncate text-xs text-ink-gray-5">
							{{ summary(run) }}
						</p>
					</div>
					<span class="shrink-0 text-xs text-ink-gray-5">{{
						timeAgo(run.creation)
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
								{{ formatDate(run.creation) }}
							</dd>
						</div>
						<div>
							<dt class="text-xs text-ink-gray-5">{{ __("Iterations") }}</dt>
							<dd class="mt-1 text-xs text-ink-gray-8">{{ run.iterations || 0 }}</dd>
						</div>
					</dl>

					<div v-if="run.input" class="mt-4">
						<p class="text-xs font-medium text-ink-gray-7">{{ __("Input") }}</p>
						<pre class="trigger-log-content">{{ run.input }}</pre>
					</div>
					<div v-if="run.output" class="mt-4">
						<p class="text-xs font-medium text-ink-gray-7">{{ __("Output") }}</p>
						<pre class="trigger-log-content">{{ run.output }}</pre>
					</div>
					<div v-if="run.error" class="mt-4">
						<p class="text-xs font-medium text-ink-red-4">{{ __("Error") }}</p>
						<pre class="trigger-log-content text-ink-red-4">{{ run.error }}</pre>
					</div>

					<Button
						v-if="run.session"
						class="mt-4"
						variant="subtle"
						@click="openSession(run.session)"
					>
						<template #prefix>
							<FeatherIcon name="message-circle" class="h-3.5 w-3.5" />
						</template>
						{{ __("Open session") }}
					</Button>
				</div>
			</details>
		</div>
	</DocSection>
</template>

<style scoped>
.trigger-log-content {
	@apply mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-outline-gray-1 bg-surface-white p-3 text-xs leading-relaxed text-ink-gray-7;
}
</style>
