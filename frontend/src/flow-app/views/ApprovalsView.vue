<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import MarkdownText from "@/components/MarkdownText.vue";
import SearchInput from "@/components/SearchInput.vue";
import { Badge, Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { decideTriggerApproval, loadTriggerApprovals } from "@/api/approvals";

// Paused runs stay on the board until the background resume picks them up.
const REFRESH_MS = 15000;

const router = useRouter();
const loading = ref(true);
const query = ref("");
const approvals = ref([]);
// run name -> decision being sent, so its buttons stay disabled until it leaves the board
const deciding = ref({});
let timer = 0;

const filtered = computed(() => {
	const value = query.value.trim().toLowerCase();
	if (!value) return approvals.value;
	return approvals.value.filter((run) =>
		[run.trigger_title, run.agent, run.reference_doctype, run.reference_name].some((field) =>
			(field || "").toLowerCase().includes(value),
		),
	);
});

onMounted(() => {
	refresh();
	timer = setInterval(() => refresh({ quiet: true }), REFRESH_MS);
});
onUnmounted(() => clearInterval(timer));

async function refresh({ quiet = false } = {}) {
	if (!quiet) loading.value = true;
	try {
		approvals.value = await loadTriggerApprovals();
	} catch (error) {
		if (!quiet) showError(error, __("Could not load approvals."));
	} finally {
		loading.value = false;
	}
}

async function decide(run, decision) {
	deciding.value = { ...deciding.value, [run.name]: decision };
	try {
		await decideTriggerApproval(run.name, decision);
		approvals.value = approvals.value.filter((item) => item.name !== run.name);
		frappe.show_alert({
			message:
				decision === "Approve"
					? __("Approved. The trigger run is continuing in the background.")
					: __("Denied. The trigger run will stop."),
			indicator: decision === "Approve" ? "green" : "orange",
		});
	} catch (error) {
		const { [run.name]: _, ...rest } = deciding.value;
		deciding.value = rest;
		showError(error, __("Could not send the decision."));
	}
}

function confirmDeny(run) {
	frappe.confirm(__("Deny this action? The trigger run will stop."), () => decide(run, "Deny"));
}

function referenceLabel(run) {
	return [run.reference_doctype, run.reference_name].filter(Boolean).join(" · ") || __("Scheduled run");
}

function openReference(run) {
	if (run.reference_doctype && run.reference_name) {
		frappe.set_route("Form", run.reference_doctype, run.reference_name);
	}
}

function openSession(run) {
	router.push({ name: "chat-session", params: { session: run.session } });
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
			<div>
				<h1 class="text-lg font-normal text-ink-gray-9">{{ __("Trigger Approvals") }}</h1>
				<p class="mt-0.5 text-sm text-ink-gray-5">
					{{ __("Trigger runs waiting for you to approve an action before they continue.") }}
				</p>
			</div>
			<Button
				icon="refresh-cw"
				variant="ghost"
				:loading="loading"
				:aria-label="__('Refresh approvals')"
				@click="refresh()"
			/>
		</header>

		<div class="px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search approvals…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div class="flow-scrollbar min-h-0 flex-1 overflow-y-auto px-6 pb-8">
			<div v-if="loading && !approvals.length" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>
			<div v-else-if="!filtered.length" class="flex flex-col items-center py-16 text-center">
				<FeatherIcon name="check-circle" class="mb-3 h-8 w-8 text-ink-gray-4" />
				<p class="font-normal text-ink-gray-8">{{ __("Nothing waiting for approval") }}</p>
				<p class="mt-1 text-sm font-normal text-ink-gray-5">
					{{
						query.trim()
							? __("Try a different search.")
							: __("Trigger runs without auto approval appear here when they need you.")
					}}
				</p>
			</div>
			<div v-else class="flex flex-col gap-4">
				<article
					v-for="run in filtered"
					:key="run.name"
					class="flex flex-col gap-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4"
				>
					<div class="flex items-start gap-3">
						<span
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2"
						>
							<FeatherIcon name="zap" class="h-4 w-4 text-ink-gray-6" />
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-semibold text-ink-gray-9">
								{{ run.trigger_title }}
							</p>
							<p class="truncate text-xs font-normal text-ink-gray-5">
								{{ run.agent }} ·
								<button
									class="hover:text-ink-gray-8 hover:underline"
									:disabled="!run.reference_name"
									@click="openReference(run)"
								>
									{{ referenceLabel(run) }}
								</button>
							</p>
						</div>
						<Badge
							variant="subtle"
							theme="orange"
							:label="run.questions.length > 1 ? __('{0} actions', [run.questions.length]) : __('1 action')"
						/>
					</div>

					<div
						v-for="question in run.questions"
						:key="question.key"
						class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-8"
					>
						<MarkdownText :part="{ text: question.prompt }" />
					</div>

					<div
						class="flex flex-wrap items-center justify-between gap-2 border-t border-outline-gray-1 pt-3"
					>
						<p class="text-xs font-normal text-ink-gray-5">
							{{ __("Waiting since {0}", [timeAgo(run.creation)]) }} · {{ run.owner }}
						</p>
						<div class="flex items-center gap-2">
							<Button variant="ghost" @click="openSession(run)">
								{{ __("Open chat") }}
							</Button>
							<template v-if="run.needs_confirmation">
								<Button
									:loading="deciding[run.name] === 'Deny'"
									:disabled="!!deciding[run.name]"
									@click="confirmDeny(run)"
								>
									{{ __("Deny") }}
								</Button>
								<Button
									variant="solid"
									:loading="deciding[run.name] === 'Approve'"
									:disabled="!!deciding[run.name]"
									@click="decide(run, 'Approve')"
								>
									{{ __("Approve") }}
								</Button>
							</template>
							<span v-else class="text-xs text-ink-gray-5">
								{{ __("The agent asked a question. Answer it in chat.") }}
							</span>
						</div>
					</div>
				</article>
			</div>
		</div>
	</main>
</template>
