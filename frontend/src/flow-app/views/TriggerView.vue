<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import PanelDropdown from "@/components/PanelDropdown.vue";
import DocSection from "@/components/DocSection.vue";
import TriggerLogs from "../components/TriggerLogs.vue";
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
import {
	createTrigger,
	loadTrigger,
	loadTriggerAgents,
	loadTriggerDoctypes,
	loadTriggerUsers,
	renameTrigger,
	updateTrigger,
} from "@/api/triggers";

const props = defineProps({
	name: { type: String, default: "" },
	isNew: { type: Boolean, default: false },
});

const EVENT_ITEMS = ["DocType Event", "Scheduled"].map((value) => ({
	label: __(value),
	value,
}));
const DOC_EVENT_ITEMS = [
	{ label: __("After Insert"), value: "after_insert" },
	{ label: __("On Update"), value: "on_update" },
	{ label: __("On Submit"), value: "on_submit" },
	{ label: __("On Cancel"), value: "on_cancel" },
	{ label: __("On Trash"), value: "on_trash" },
];

const router = useRouter();
const loading = ref(!props.isNew);
const saving = ref(false);
const agents = ref([]);
const doctypes = ref([]);
const users = ref([]);
const form = reactive(blankTrigger());
const snapshot = ref("");

const pageTitle = computed(() =>
	props.isNew ? form.title || __("New Trigger") : form.title || props.name,
);
const breadcrumbs = computed(() => [
	{ label: __("Triggers"), route: { name: "triggers" } },
	props.isNew
		? { label: __("New Trigger"), route: { name: "trigger-new" } }
		: { label: pageTitle.value, route: { name: "trigger", params: { name: props.name } } },
]);
const canEdit = computed(
	() =>
		frappe.session.user === "Administrator" ||
		(frappe.user_roles || []).includes("System Manager"),
);
const canSave = computed(() => {
	if (!form.title.trim() || !form.agent || !form.prompt_template.trim()) return false;
	if (form.event === "Scheduled") return !!form.cron_expression.trim();
	return !!form.target_doctype && !!form.doc_event;
});
const dirty = computed(() => !loading.value && JSON.stringify(formState()) !== snapshot.value);
const agentItems = computed(() => [
	{ label: __("Select an agent"), value: "" },
	...agents.value.map((agent) => ({ label: agent.title || agent.name, value: agent.name })),
]);
const doctypeItems = computed(() => [
	{ label: __("Select a DocType"), value: "" },
	...doctypes.value.map((doctype) => ({ label: doctype.name, value: doctype.name })),
]);
const userItems = computed(() => [
	{ label: __("Use trigger owner"), value: "" },
	...users.value.map((user) => ({
		label: user.full_name ? `${user.full_name} (${user.name})` : user.name,
		value: user.name,
	})),
]);

onMounted(load);

async function load() {
	try {
		const [agentRows, doctypeRows, userRows] = await Promise.all([
			loadTriggerAgents(),
			loadTriggerDoctypes(),
			loadTriggerUsers().catch(() => []),
		]);
		agents.value = agentRows;
		doctypes.value = doctypeRows;
		users.value = userRows;
		if (!props.isNew) Object.assign(form, normalize(await loadTrigger(props.name)));
	} catch (error) {
		showError(error, __("Could not load trigger."));
		goBack();
		return;
	} finally {
		loading.value = false;
	}
	snapshotForm();
}

async function save() {
	if (!canEdit.value || !canSave.value || !dirty.value) return;
	saving.value = true;
	try {
		const values = editableValues();
		if (props.isNew) {
			await createTrigger({ doctype: "Flow Trigger", title: form.title.trim(), ...values });
			frappe.show_alert({ message: __("Trigger created."), indicator: "green" });
		} else {
			let name = props.name;
			const newTitle = form.title.trim();
			if (newTitle !== name) name = await renameTrigger(name, newTitle);
			await updateTrigger(name, values);
			frappe.show_alert({ message: __("Trigger updated."), indicator: "green" });
		}
		goBack();
	} catch (error) {
		showError(error, __("Could not save trigger."));
	} finally {
		saving.value = false;
	}
}

function editableValues() {
	const isScheduled = form.event === "Scheduled";
	return {
		agent: form.agent,
		event: form.event,
		enabled: form.enabled ? 1 : 0,
		auto_approve: form.auto_approve ? 1 : 0,
		run_as: form.run_as || "",
		target_doctype: isScheduled ? "" : form.target_doctype,
		doc_event: isScheduled ? "" : form.doc_event,
		cron_expression: isScheduled ? form.cron_expression.trim() : "",
		condition: form.condition.trim(),
		prompt_template: form.prompt_template.trim(),
	};
}

function formState() {
	return {
		title: form.title,
		...editableValues(),
	};
}

function snapshotForm() {
	snapshot.value = JSON.stringify(formState());
}

function blankTrigger() {
	return {
		title: "",
		agent: "",
		event: "DocType Event",
		enabled: true,
		auto_approve: false,
		run_as: "",
		target_doctype: "",
		doc_event: "after_insert",
		cron_expression: "",
		last_fired_at: "",
		condition: "",
		prompt_template: "",
	};
}

function normalize(doc) {
	return {
		...blankTrigger(),
		...doc,
		enabled: !!doc.enabled,
		auto_approve: !!doc.auto_approve,
	};
}

function selectedLabel(items, value, fallback) {
	return items.find((item) => item.value === value)?.label || fallback;
}

function formatDatetime(value) {
	if (!value) return __("Never");
	return window.moment ? moment(value).format("lll") : value;
}

function goBack() {
	router.push({ name: "triggers" });
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
					v-if="canEdit"
					variant="solid"
					:disabled="!canSave || !dirty"
					:loading="saving"
					@click="save"
				>
					{{ props.isNew ? __("Create Trigger") : __("Save") }}
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
								:label="__('Title')"
								:placeholder="__('e.g. Follow up on overdue invoices')"
								:model-value="form.title"
								@update:model-value="(value) => (form.title = value)"
							/>

							<div class="grid gap-4 md:grid-cols-2">
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
										hide-scrollbar
										@update:model-value="(value) => (form.agent = value)"
									>
										<template #trigger="{ toggle }">
											<button
												type="button"
												class="trigger-select"
												@click="toggle"
											>
												<span class="truncate">{{
													selectedLabel(
														agentItems,
														form.agent,
														__("Select an agent"),
													)
												}}</span>
												<FeatherIcon
													name="chevron-down"
													class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
												/>
											</button>
										</template>
									</PanelDropdown>
								</div>

								<div>
									<label class="mb-1.5 block text-xs text-ink-gray-5">{{
										__("Event")
									}}</label>
									<PanelDropdown
										:items="EVENT_ITEMS"
										:model-value="form.event"
										placement="bottom"
										match-trigger-width
										@update:model-value="(value) => (form.event = value)"
									>
										<template #trigger="{ toggle }">
											<button
												type="button"
												class="trigger-select"
												@click="toggle"
											>
												<span>{{
													selectedLabel(
														EVENT_ITEMS,
														form.event,
														__("Select an event"),
													)
												}}</span>
												<FeatherIcon
													name="chevron-down"
													class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
												/>
											</button>
										</template>
									</PanelDropdown>
								</div>
							</div>

							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{
									__("Run As")
								}}</label>
								<PanelDropdown
									:items="userItems"
									:model-value="form.run_as"
									placement="bottom"
									searchable
									match-trigger-width
									@update:model-value="(value) => (form.run_as = value)"
								>
									<template #trigger="{ toggle }">
										<button
											type="button"
											class="trigger-select"
											@click="toggle"
										>
											<span class="truncate">{{
												selectedLabel(
													userItems,
													form.run_as,
													__("Use trigger owner"),
												)
											}}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>
								<p class="mt-1.5 text-xs text-ink-gray-5">
									{{
										__(
											"The agent's tools use this user's permissions. Leave empty to use the trigger owner.",
										)
									}}
								</p>
							</div>

							<Switch
								v-model="form.enabled"
								:label="__('Enabled')"
								:description="
									__('Off = this trigger stays saved but will not fire.')
								"
							/>
							<Switch
								v-model="form.auto_approve"
								:label="__('Auto approve tool calls')"
								:description="
									__(
										'Allow unattended runs to continue without waiting for tool approval.',
									)
								"
							/>
						</div>
					</DocSection>

					<DocSection :label="__('When')" :collapsible="false">
						<div
							v-if="form.event === 'DocType Event'"
							class="grid gap-4 md:grid-cols-2"
						>
							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{
									__("Target DocType")
								}}</label>
								<PanelDropdown
									:items="doctypeItems"
									:model-value="form.target_doctype"
									placement="bottom"
									searchable
									match-trigger-width
									@update:model-value="(value) => (form.target_doctype = value)"
								>
									<template #trigger="{ toggle }">
										<button
											type="button"
											class="trigger-select"
											@click="toggle"
										>
											<span class="truncate">{{
												selectedLabel(
													doctypeItems,
													form.target_doctype,
													__("Select a DocType"),
												)
											}}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>
							</div>
							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{
									__("Document Event")
								}}</label>
								<PanelDropdown
									:items="DOC_EVENT_ITEMS"
									:model-value="form.doc_event"
									placement="bottom"
									match-trigger-width
									@update:model-value="(value) => (form.doc_event = value)"
								>
									<template #trigger="{ toggle }">
										<button
											type="button"
											class="trigger-select"
											@click="toggle"
										>
											<span>{{
												selectedLabel(
													DOC_EVENT_ITEMS,
													form.doc_event,
													__("Select an event"),
												)
											}}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>
							</div>
						</div>
						<div v-else class="grid gap-4 md:grid-cols-2">
							<TextInput
								type="text"
								:label="__('Cron Expression')"
								:placeholder="__('e.g. 0 9 * * 5')"
								:model-value="form.cron_expression"
								:description="__('Standard 5-field cron in the site timezone.')"
								@update:model-value="(value) => (form.cron_expression = value)"
							/>
							<TextInput
								type="text"
								:label="__('Last Fired At')"
								:model-value="formatDatetime(form.last_fired_at)"
								disabled
							/>
						</div>
					</DocSection>

					<DocSection :label="__('Condition')">
						<div class="trigger-code">
							<Textarea
								:rows="5"
								:placeholder="__(`Optional: doc.status == 'Open'`)"
								:model-value="form.condition"
								@update:model-value="(value) => (form.condition = value)"
							/>
						</div>
						<p class="mt-2 text-xs text-ink-gray-5">
							{{
								__(
									"Optional Python expression over doc. Multi-line conditions must assign the final value to result.",
								)
							}}
						</p>
					</DocSection>

					<DocSection :label="__('Prompt')" :collapsible="false">
						<div class="trigger-code">
							<Textarea
								:rows="9"
								:placeholder="
									__(
										'Tell the agent what to do. You can use {{ doc }} and {{ now }} in this Jinja template.',
									)
								"
								:model-value="form.prompt_template"
								@update:model-value="(value) => (form.prompt_template = value)"
							/>
						</div>
						<p class="mt-2 text-xs text-ink-gray-5">
							{{
								__(
									"This Jinja template becomes the agent's input whenever the trigger fires.",
								)
							}}
						</p>
					</DocSection>

					<TriggerLogs v-if="!props.isNew" :trigger="props.name" />
				</div>
			</fieldset>
		</div>
	</main>
</template>

<style scoped>
.trigger-select {
	@apply flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2;
}

.trigger-code :deep(textarea) {
	font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
	font-size: 13px !important;
}
</style>
