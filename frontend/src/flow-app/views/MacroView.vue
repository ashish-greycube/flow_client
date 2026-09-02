<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import ViewHeader from "../components/ViewHeader.vue";
import FieldControl from "../components/FieldControl.vue";
import ToggleControl from "../components/ToggleControl.vue";
import { Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { createMacro, loadMacro, loadMacroAgents, runMacro, saveMacro } from "@/api/macros";

const props = defineProps({
	name: { type: String, default: "" },
	isNew: { type: Boolean, default: false },
});
const router = useRouter();
const loading = ref(!props.isNew);
const saving = ref(false);
const running = ref(false);
const agents = ref([]);
const form = reactive(blankMacro());

const title = computed(() =>
	props.isNew ? form.macro_name || __("New Macro") : form.macro_name || props.name,
);
const canEdit = computed(
	() =>
		props.isNew ||
		form.owner === frappe.session.user ||
		frappe.session.user === "Administrator",
);
const agentOptions = computed(() => [
	{ label: __("Select an agent"), value: "" },
	...agents.value.map((agent) => ({ label: agent.title || agent.name, value: agent.name })),
]);

onMounted(async () => {
	try {
		agents.value = await loadMacroAgents();
		if (!props.isNew) Object.assign(form, normalize(await loadMacro(props.name)));
	} catch (error) {
		showError(error, __("Could not load macro."));
	} finally {
		loading.value = false;
	}
});

async function save() {
	const doc = payload();
	if (!doc.macro_name || !doc.agent || !doc.steps.length) {
		showError(null, __("Macro name, agent, and at least one prompt are required."));
		return;
	}
	saving.value = true;
	try {
		const saved = props.isNew ? await createMacro(doc) : await saveMacro(doc);
		Object.assign(form, normalize(saved));
		frappe.show_alert({ message: __("Macro saved."), indicator: "green" });
		if (props.isNew) router.replace({ name: "macro", params: { name: saved.name } });
	} catch (error) {
		showError(error, __("Could not save macro."));
	} finally {
		saving.value = false;
	}
}

async function run() {
	running.value = true;
	try {
		const result = await runMacro(props.name);
		router.push({ name: "macro-run", params: { name: result.macro_run } });
	} catch (error) {
		showError(error, __("Could not run macro."));
	} finally {
		running.value = false;
	}
}

function addStep() {
	if (form.steps.length < 25) form.steps.push({ label: "", prompt: "", model_override: "" });
}

function removeStep(index) {
	if (form.steps.length > 1) form.steps.splice(index, 1);
}

function payload() {
	return {
		doctype: "Flow Macro",
		...(props.isNew ? {} : { name: props.name }),
		macro_name: form.macro_name.trim(),
		description: form.description.trim(),
		agent: form.agent,
		enabled: form.enabled ? 1 : 0,
		stop_on_error: form.stop_on_error ? 1 : 0,
		auto_approve: form.auto_approve ? 1 : 0,
		schedule_enabled: form.schedule_enabled ? 1 : 0,
		schedule_frequency: form.schedule_frequency,
		schedule_time: form.schedule_time || "09:00",
		cron_expression: form.schedule_frequency === "Cron" ? form.cron_expression.trim() : "",
		steps: form.steps
			.map((step) => ({
				doctype: "Flow Macro Step",
				label: (step.label || "").trim(),
				prompt: (step.prompt || "").trim(),
				model_override: step.model_override || "",
			}))
			.filter((step) => step.prompt),
	};
}

function blankMacro() {
	return {
		macro_name: "",
		description: "",
		agent: "",
		enabled: true,
		stop_on_error: true,
		auto_approve: false,
		schedule_enabled: false,
		schedule_frequency: "Daily",
		schedule_time: "09:00",
		cron_expression: "",
		steps: [{ label: "", prompt: "", model_override: "" }],
	};
}

function normalize(doc) {
	return {
		...blankMacro(),
		...doc,
		enabled: !!doc.enabled,
		stop_on_error: !!doc.stop_on_error,
		auto_approve: !!doc.auto_approve,
		schedule_enabled: !!doc.schedule_enabled,
		schedule_time: String(doc.schedule_time || "09:00").slice(0, 5),
		steps: (doc.steps || []).map((step) => ({ ...step })),
	};
}

function showError(error, fallback) {
	frappe.show_alert({ message: error?.message || fallback, indicator: "red" });
}
</script>

<template>
	<main class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white">
		<ViewHeader :title="title" back @back="router.push({ name: 'macros' })">
			<Button
				v-if="!isNew && canEdit"
				variant="subtle"
				:loading="running"
				:disabled="!form.enabled"
				@click="run"
			>
				<template #prefix><FeatherIcon name="play" class="h-3.5 w-3.5" /></template>
				{{ __("Run") }}
			</Button>
			<Button v-if="canEdit" variant="solid" :loading="saving" @click="save">
				{{ __("Save") }}
			</Button>
		</ViewHeader>

		<div v-if="loading" class="flex min-h-0 flex-1 items-center justify-center">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>
		<div v-else class="flow-scrollbar min-h-0 flex-1 overflow-y-auto">
			<fieldset :disabled="!canEdit" class="w-full space-y-6 px-6 py-6 disabled:opacity-75">
				<section class="rounded-xl border border-outline-gray-1 p-5">
					<h2 class="mb-4 text-sm font-medium text-ink-gray-9">
						{{ __("Macro details") }}
					</h2>
					<div class="grid gap-4 md:grid-cols-2">
						<FieldControl
							v-model="form.macro_name"
							:label="__('Macro Name')"
							:required="true"
						/>
						<FieldControl
							v-model="form.agent"
							type="select"
							:label="__('Agent')"
							:options="agentOptions"
							:required="true"
						/>
						<FieldControl
							v-model="form.description"
							type="textarea"
							:label="__('Description')"
							class="md:col-span-2"
						/>
					</div>
					<div class="mt-4 grid gap-3 md:grid-cols-3">
						<ToggleControl v-model="form.enabled" :label="__('Enabled')" />
						<ToggleControl v-model="form.stop_on_error" :label="__('Stop on error')" />
						<ToggleControl
							v-model="form.auto_approve"
							:label="__('Auto approve tool calls')"
						/>
					</div>
				</section>

				<section class="rounded-xl border border-outline-gray-1 p-5">
					<div class="flex items-center justify-between">
						<div>
							<h2 class="text-sm font-medium text-ink-gray-9">
								{{ __("Schedule") }}
							</h2>
							<p class="mt-1 text-sm font-normal text-ink-gray-5">
								{{ __("Run this macro automatically at site-local time.") }}
							</p>
						</div>
						<ToggleControl v-model="form.schedule_enabled" />
					</div>
					<div v-if="form.schedule_enabled" class="mt-4 grid gap-4 md:grid-cols-2">
						<FieldControl
							v-model="form.schedule_frequency"
							type="select"
							:label="__('Frequency')"
							:options="['Daily', 'Weekly', 'Monthly', 'Cron']"
						/>
						<FieldControl
							v-if="form.schedule_frequency !== 'Cron'"
							v-model="form.schedule_time"
							type="time"
							:label="__('Time of day')"
						/>
						<FieldControl
							v-else
							v-model="form.cron_expression"
							:label="__('Cron expression')"
							:required="true"
						/>
					</div>
				</section>

				<section class="rounded-xl border border-outline-gray-1 p-5">
					<div class="mb-4">
						<div>
							<h2 class="text-sm font-medium text-ink-gray-9">
								{{ __("Steps") }}
							</h2>
							<p class="mt-1 text-sm font-normal text-ink-gray-5">
								{{ __("Prompts run in this order in one Flow session.") }}
							</p>
						</div>
					</div>
					<div class="space-y-3">
						<div
							v-for="(step, index) in form.steps"
							:key="index"
							class="rounded-lg bg-surface-gray-1 p-4"
						>
							<div class="mb-3 flex items-center justify-between">
								<p class="text-sm font-normal text-ink-gray-8">
									{{ __("Step {0}", [index + 1]) }}
								</p>
								<Button
									variant="ghost"
									icon="x"
									:disabled="form.steps.length === 1"
									@click="removeStep(index)"
								/>
							</div>
							<div class="grid gap-3">
								<FieldControl v-model="step.label" :label="__('Label')" />
								<FieldControl
									v-model="step.prompt"
									type="textarea"
									:label="__('Prompt')"
									:required="true"
								/>
							</div>
						</div>
					</div>
					<button
						type="button"
						class="mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-dashed border-outline-gray-2 text-sm font-normal text-ink-gray-6 hover:border-outline-gray-3 hover:bg-surface-gray-1 hover:text-ink-gray-8 disabled:cursor-not-allowed disabled:opacity-50"
						:disabled="form.steps.length >= 25"
						@click="addStep"
					>
						<FeatherIcon name="plus" class="h-4 w-4" />
						{{ __("Add another step") }}
					</button>
				</section>
			</fieldset>
		</div>
	</main>
</template>
