<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import PanelDropdown from "@/components/PanelDropdown.vue";
import DocSection from "@/components/DocSection.vue";
import MacroLogs from "../components/MacroLogs.vue";
import {
	Badge,
	Breadcrumbs,
	Button,
	FeatherIcon,
	Spinner,
	Switch,
	Textarea,
	TextInput,
} from "@/lib/ui";
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
const snapshot = ref("");

const pageTitle = computed(() =>
	props.isNew ? form.macro_name || __("New Macro") : form.macro_name || props.name,
);
const breadcrumbs = computed(() => [
	{ label: __("Macros"), route: { name: "macros" } },
	props.isNew
		? { label: __("New Macro"), route: { name: "macro-new" } }
		: { label: pageTitle.value, route: { name: "macro", params: { name: props.name } } },
]);
const canEdit = computed(
	() =>
		props.isNew ||
		form.owner === frappe.session.user ||
		frappe.session.user === "Administrator",
);
const canSave = computed(
	() => form.macro_name.trim() && form.agent && form.steps.some((step) => step.prompt.trim()),
);
const dirty = computed(() => !loading.value && JSON.stringify(formState()) !== snapshot.value);
const agentItems = computed(() => [
	{ label: __("Select an agent"), value: "" },
	...agents.value.map((agent) => ({ label: agent.title || agent.name, value: agent.name })),
]);
const frequencyItems = computed(() =>
	["Daily", "Weekly", "Monthly", "Cron"].map((value) => ({ label: __(value), value })),
);

onMounted(load);

async function load() {
	try {
		agents.value = await loadMacroAgents();
		if (!props.isNew) Object.assign(form, normalize(await loadMacro(props.name)));
	} catch (error) {
		showError(error, __("Could not load macro."));
		goBack();
		return;
	} finally {
		loading.value = false;
	}
	snapshotForm();
}

async function save() {
	if (!canSave.value || !dirty.value) return;
	saving.value = true;
	try {
		const saved = props.isNew ? await createMacro(payload()) : await saveMacro(payload());
		Object.assign(form, normalize(saved));
		snapshotForm();
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

function goBack() {
	router.push({ name: "macros" });
}

function snapshotForm() {
	snapshot.value = JSON.stringify(formState());
}

function formState() {
	return {
		macro_name: form.macro_name,
		description: form.description,
		agent: form.agent,
		enabled: !!form.enabled,
		stop_on_error: !!form.stop_on_error,
		auto_approve: !!form.auto_approve,
		schedule_enabled: !!form.schedule_enabled,
		schedule_frequency: form.schedule_frequency,
		schedule_time: form.schedule_time,
		cron_expression: form.cron_expression,
		steps: form.steps.map((step) => ({
			label: step.label || "",
			prompt: step.prompt || "",
			model_override: step.model_override || "",
		})),
	};
}

function payload() {
	return {
		// frappe.client.save expects loaded metadata and child-row identities.
		...form,
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
				...step,
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
	<main
		class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9"
	>
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<Breadcrumbs class="flow-editor-breadcrumbs" :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<Button variant="subtle" :disabled="saving" @click="goBack">{{
					__("Cancel")
				}}</Button>
				<Button
					v-if="!props.isNew && canEdit"
					variant="subtle"
					:loading="running"
					:disabled="!form.enabled || dirty"
					@click="run"
				>
					<template #prefix><FeatherIcon name="play" class="h-3.5 w-3.5" /></template>
					{{ __("Run") }}
				</Button>
				<Button
					v-if="canEdit"
					variant="solid"
					:disabled="!canSave || !dirty"
					:loading="saving"
					@click="save"
				>
					{{ props.isNew ? __("Create Macro") : __("Save") }}
				</Button>
			</div>
		</header>

		<div v-if="loading" class="flex min-h-0 flex-1 items-center justify-center">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>
		<div v-else class="flow-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-6">
			<fieldset :disabled="!canEdit || saving" class="mx-auto max-w-3xl disabled:opacity-75">
				<div class="flex items-center gap-3">
					<h1 class="min-w-0 truncate text-2xl font-semibold text-ink-gray-9">
						{{ pageTitle }}
					</h1>
					<Badge v-if="dirty" variant="subtle" theme="orange" :label="__('Not Saved')" />
				</div>

				<div class="mt-4">
					<DocSection :label="__('Details')" :collapsible="false">
						<div class="space-y-4">
							<TextInput
								type="text"
								:label="__('Macro Name')"
								:placeholder="__('e.g. Weekly overdue invoice check')"
								:model-value="form.macro_name"
								@update:model-value="(value) => (form.macro_name = value)"
							/>

							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{
									__("Agent")
								}}</label>
								<PanelDropdown
									:items="agentItems"
									:model-value="form.agent"
									placement="bottom"
									searchable
									match-trigger-width
									@update:model-value="(value) => (form.agent = value)"
								>
									<template #trigger="{ toggle }">
										<button
											type="button"
											class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2"
											@click="toggle"
										>
											<span class="truncate">
												{{
													agentItems.find(
														(agent) => agent.value === form.agent,
													)?.label
												}}
											</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>
							</div>

							<div class="macro-textarea">
								<Textarea
									:label="__('Description')"
									:rows="3"
									:placeholder="__('Describe what this macro does.')"
									:model-value="form.description"
									@update:model-value="(value) => (form.description = value)"
								/>
							</div>

							<Switch
								v-model="form.enabled"
								:label="__('Enabled')"
								:description="
									__('Off = this macro cannot be run manually or on a schedule.')
								"
							/>
							<Switch
								v-model="form.stop_on_error"
								:label="__('Stop on error')"
								:description="__('Stop the remaining steps when one step fails.')"
							/>
							<Switch
								v-model="form.auto_approve"
								:label="__('Auto approve tool calls')"
								:description="
									__(
										'Allow this macro to continue without pausing for tool approval.',
									)
								"
							/>
						</div>
					</DocSection>

					<DocSection :label="__('Schedule')" :collapsible="false">
						<div class="space-y-4">
							<Switch
								v-model="form.schedule_enabled"
								:label="__('Run on a schedule')"
								:description="
									__('Run this macro automatically at site-local time.')
								"
							/>
							<div v-if="form.schedule_enabled" class="grid gap-4 md:grid-cols-2">
								<div>
									<label class="mb-1.5 block text-xs text-ink-gray-5">{{
										__("Frequency")
									}}</label>
									<PanelDropdown
										:items="frequencyItems"
										:model-value="form.schedule_frequency"
										placement="bottom"
										match-trigger-width
										@update:model-value="
											(value) => (form.schedule_frequency = value)
										"
									>
										<template #trigger="{ toggle }">
											<button
												type="button"
												class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2"
												@click="toggle"
											>
												<span>{{ __(form.schedule_frequency) }}</span>
												<FeatherIcon
													name="chevron-down"
													class="h-3.5 w-3.5 text-ink-gray-5"
												/>
											</button>
										</template>
									</PanelDropdown>
								</div>
								<TextInput
									v-if="form.schedule_frequency !== 'Cron'"
									type="time"
									:label="__('Time of day')"
									:model-value="form.schedule_time"
									@update:model-value="(value) => (form.schedule_time = value)"
								/>
								<TextInput
									v-else
									type="text"
									:label="__('Cron expression')"
									:placeholder="__('e.g. 0 9 * * 5')"
									:model-value="form.cron_expression"
									@update:model-value="(value) => (form.cron_expression = value)"
								/>
							</div>
						</div>
					</DocSection>

					<DocSection :label="__('Steps')" :collapsible="false">
						<p class="mb-3 text-sm text-ink-gray-5">
							{{ __("Prompts run in this order in one Flow session.") }}
						</p>
						<div class="space-y-3">
							<div
								v-for="(step, index) in form.steps"
								:key="index"
								class="rounded-lg border border-outline-gray-1 bg-surface-white p-4"
							>
								<div class="mb-3 flex items-center justify-between">
									<p class="text-sm font-medium text-ink-gray-8">
										{{ __("Step {0}", [index + 1]) }}
									</p>
									<Button
										variant="ghost"
										icon="x"
										:disabled="form.steps.length === 1"
										@click="removeStep(index)"
									/>
								</div>
								<div class="space-y-3">
									<TextInput
										type="text"
										:label="__('Label')"
										:placeholder="__('Optional step label')"
										:model-value="step.label"
										@update:model-value="(value) => (step.label = value)"
									/>
									<div class="macro-textarea">
										<Textarea
											:label="__('Prompt')"
											:rows="3"
											:placeholder="
												__('What should the agent do in this step?')
											"
											:model-value="step.prompt"
											@update:model-value="(value) => (step.prompt = value)"
										/>
									</div>
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
					</DocSection>

					<MacroLogs v-if="!props.isNew" :macro="props.name" />
				</div>
			</fieldset>
		</div>
	</main>
</template>

<style scoped>
.macro-textarea :deep(textarea) {
	font-size: 14px !important;
}
</style>
