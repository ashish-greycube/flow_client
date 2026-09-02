<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PanelDropdown from "@/components/PanelDropdown.vue";
import DocSection from "@/components/DocSection.vue";
import { Button, FeatherIcon, Spinner, Badge, TextInput, Textarea, Switch, Breadcrumbs } from "@/lib/ui";
import { __ } from "@/lib/translate";
import {
	loadModels,
	loadTools,
	loadKnowledgeBases,
	getAgent,
	createAgent,
	saveAgent,
	renameAgent,
} from "@/api/client";

// Full page for both Create and Edit (routed at /agents/new and
// /agents/:name) — a dialog previously covered this, but a page keeps the
// sidebar visible and gives each agent its own real, bookmarkable URL.
// Styled after Jarvis's Macro new/edit page (frontend/src/pages/macros/
// MacroDetail.vue): breadcrumbs + actions header, a title row with a "Not
// Saved" badge, fields grouped under DocSections. The section split (Details
// / Instructions / Tools / Knowledge Base) mirrors the Flow Agent doctype's
// own section breaks, same as the Desk form would render them.
const route = useRoute();
const router = useRouter();

const agentName = computed(() => route.params.name || null);
const isEdit = computed(() => !!agentName.value);

const loading = ref(false);
const saving = ref(false);
const models = ref([]);
const tools = ref([]);
const knowledgeBases = ref([]);
// Flow Agent is `autoname: "field:title"` — the title field is locked in
// sync with the docname (Document._sync_autoname_field reverts any other
// change to it on save), and renames are blocked outright for built-in
// agents (flow_agent.py's before_rename). Title is only actually editable
// when neither of those applies. Preserved verbatim through every save (see
// saveAgent's note in api/client.js) since this form never exposes it.
const isSystemGenerated = ref(false);
// frappe.client.save reconstructs the doc from scratch (frappe.get_doc(dict)),
// not by loading + merging onto the DB row — so any standard field it omits
// reads as empty on the new in-memory doc. `modified` has to be the real DB
// value or Document.check_if_latest() throws TimestampMismatchError (it
// compares against empty, which never matches); `creation`/`owner` have to be
// the real values too or validate_set_only_once() throws "Value cannot be
// changed for Created On" — creation/owner are unconditionally set-only-once
// for every doctype (frappe/model/meta.py's standard_set_once_fields).
const docMeta = ref({ modified: null, creation: null, owner: null });

const form = reactive({
	title: "",
	model: null,
	max_iterations: null,
	instructions: "",
	enabled: true,
	tools: [], // [{ tool, permission }]
	knowledge_bases: [], // [knowledge_base name, ...]
});
// Saved-state copy for the dirty compare, set once load() settles.
const snapshot = ref(null);

const modelItems = computed(() => models.value.map((m) => ({ value: m.name, label: m.title })));
const toolItems = computed(() => tools.value.map((t) => ({ value: t.name, label: t.title })));
const PERMISSION_ITEMS = [
	{ value: "", label: __("Default") },
	{ value: "Always Allow", label: __("Always Allow") },
	{ value: "Needs Approval", label: __("Needs Approval") },
	{ value: "Blocked", label: __("Blocked") },
];
const knowledgeBaseItems = computed(() =>
	knowledgeBases.value.map((k) => ({ value: k.name, label: k.title }))
);
const availableKnowledgeBaseItems = computed(() =>
	knowledgeBaseItems.value.filter((i) => !form.knowledge_bases.includes(i.value))
);

function toolLabel(name) {
	return toolItems.value.find((t) => t.value === name)?.label || __("Select a tool");
}
function permissionLabel(value) {
	return PERMISSION_ITEMS.find((p) => p.value === (value || ""))?.label;
}
function knowledgeBaseLabel(name) {
	return knowledgeBaseItems.value.find((k) => k.value === name)?.label || name;
}

function addToolRow() {
	form.tools.push({ tool: null, permission: "" });
}
function removeToolRow(index) {
	form.tools.splice(index, 1);
}
function addKnowledgeBase(name) {
	if (name && !form.knowledge_bases.includes(name)) form.knowledge_bases.push(name);
}
function removeKnowledgeBase(name) {
	form.knowledge_bases = form.knowledge_bases.filter((k) => k !== name);
}

const canSave = computed(
	() => form.title.trim() && form.model && form.instructions.trim() && !saving.value
);

function toolsKey(list) {
	return JSON.stringify(list.map((r) => [r.tool, r.permission || ""]));
}

const dirty = computed(() => {
	const snap = snapshot.value;
	if (!snap || loading.value) return false;
	return (
		(form.title || "") !== snap.title ||
		(form.model || null) !== snap.model ||
		(form.max_iterations || null) !== snap.max_iterations ||
		(form.instructions || "") !== snap.instructions ||
		(form.enabled ? 1 : 0) !== snap.enabled ||
		toolsKey(form.tools) !== snap.toolsKey ||
		JSON.stringify([...form.knowledge_bases].sort()) !== snap.knowledgeBasesJson
	);
});

const pageTitle = computed(() =>
	isEdit.value ? form.title || agentName.value : form.title || __("New Agent")
);
const breadcrumbs = computed(() => [
	{ label: __("Agents"), route: { name: "agents" } },
	isEdit.value
		? { label: pageTitle.value, route: { name: "agent-edit", params: { name: agentName.value } } }
		: { label: __("New Agent"), route: { name: "agent-new" } },
]);

function snapshotForm() {
	snapshot.value = {
		title: form.title,
		model: form.model,
		max_iterations: form.max_iterations || null,
		instructions: form.instructions,
		enabled: form.enabled ? 1 : 0,
		toolsKey: toolsKey(form.tools),
		knowledgeBasesJson: JSON.stringify([...form.knowledge_bases].sort()),
	};
}

async function load() {
	[models.value, tools.value, knowledgeBases.value] = await Promise.all([
		loadModels().catch(() => []),
		loadTools().catch(() => []),
		loadKnowledgeBases().catch(() => []),
	]);

	if (isEdit.value) {
		loading.value = true;
		try {
			const doc = await getAgent(agentName.value);
			form.title = doc.title || "";
			form.model = doc.model || null;
			form.max_iterations = doc.max_iterations || null;
			form.instructions = doc.instructions || "";
			form.enabled = !!doc.enabled;
			form.tools = (doc.tools || []).map((r) => ({ tool: r.tool, permission: r.permission || "" }));
			form.knowledge_bases = (doc.knowledge_bases || []).map((r) => r.knowledge_base);
			isSystemGenerated.value = !!doc.is_system_generated;
			docMeta.value = { modified: doc.modified, creation: doc.creation, owner: doc.owner };
		} catch (e) {
			frappe.show_alert({ message: e.message || __("Could not load agent."), indicator: "red" });
			goBack();
			return;
		} finally {
			loading.value = false;
		}
	} else {
		form.title = "";
		form.model = models.value[0]?.name || null;
		form.max_iterations = null;
		form.instructions = "";
		form.enabled = true;
		form.tools = [];
		form.knowledge_bases = [];
	}
	snapshotForm();
}
// A watcher, not onMounted: after Save this view now stays on the agent's
// own page instead of bouncing to the list, which for a fresh create means
// routing from agent-new to agent-edit for the SAME name it's about to
// receive — since both routes resolve to this one component, vue-router
// reuses the existing instance rather than remounting it, so onMounted would
// never fire again and the newly-created agent's docMeta/tools/etc would
// never load (see KnowledgeSourceFormView.vue's identical fix/note).
watch(agentName, load, { immediate: true });

function goBack() {
	router.push({ name: "agents" });
}

async function save() {
	if (!canSave.value) return;
	saving.value = true;
	try {
		const values = {
			model: form.model,
			max_iterations: form.max_iterations || null,
			instructions: form.instructions.trim(),
			enabled: form.enabled ? 1 : 0,
			tools: form.tools
				.filter((r) => r.tool)
				.map((r) => ({ tool: r.tool, permission: r.permission || null })),
			knowledge_bases: form.knowledge_bases.map((kb) => ({ knowledge_base: kb })),
		};
		let finalName;
		if (isEdit.value) {
			// Title first, and separately: renaming changes the docname, so the
			// save below must target whatever name comes back from it, not the
			// (possibly now-stale) agentName.
			let name = agentName.value;
			const newTitle = form.title.trim();
			if (!isSystemGenerated.value && newTitle !== name) {
				name = await renameAgent(name, newTitle);
				// The rename itself touches the doc, so `modified` captured at load
				// time is now stale — refetch or the save below throws
				// TimestampMismatchError against the post-rename row.
				const fresh = await getAgent(name);
				docMeta.value = { modified: fresh.modified, creation: fresh.creation, owner: fresh.owner };
			}
			await saveAgent({
				name,
				title: name,
				...docMeta.value,
				is_system_generated: isSystemGenerated.value ? 1 : 0,
				...values,
			});
			frappe.show_alert({ message: __("Agent updated."), indicator: "green" });
			finalName = name;
		} else {
			const created = await createAgent({ title: form.title.trim(), ...values });
			frappe.show_alert({ message: __("Agent created."), indicator: "green" });
			finalName = created.name;
		}
		// Stay on the agent's own page after saving instead of bouncing back to
		// the list. A rename changed the docname, so the route has to follow
		// it (the watcher above then reloads under the new name); otherwise
		// just reload in place to clear the dirty badge and refresh docMeta.
		if (agentName.value !== finalName) {
			await router.replace({ name: "agent-edit", params: { name: finalName } });
		} else {
			await load();
		}
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Could not save agent."), indicator: "red" });
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<div class="relative flex min-w-0 flex-1 flex-col bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<Breadcrumbs class="form-breadcrumbs" :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<Button variant="subtle" :disabled="saving" @click="goBack">{{ __("Cancel") }}</Button>
				<Button variant="solid" :disabled="!canSave || !dirty" :loading="saving" @click="save">{{
					isEdit ? __("Save") : __("Create Agent")
				}}</Button>
			</div>
		</header>

		<div v-if="loading" class="flex justify-center py-16">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>

		<div v-else class="flow-scrollbar flex-1 overflow-y-auto px-6 py-6">
			<div class="mx-auto max-w-3xl">
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
								:placeholder="__('e.g. Sales Analysis Agent')"
								:model-value="form.title"
								:disabled="isSystemGenerated || saving"
								:description="isSystemGenerated ? __('Built-in agents can\'t be renamed.') : ''"
								@update:model-value="(v) => (form.title = v)"
							/>

							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{ __("Model") }}</label>
								<PanelDropdown
									:items="modelItems"
									:model-value="form.model"
									:disabled="saving"
									placement="bottom"
									searchable
									match-trigger-width
									@update:model-value="(v) => (form.model = v)"
								>
									<template #trigger="{ toggle }">
										<button
											class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2"
											@click="toggle"
										>
											<span class="truncate">{{
												modelItems.find((m) => m.value === form.model)?.label ||
												__("Select a model")
											}}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>
							</div>

							<TextInput
								type="number"
								:label="__('Max Iterations')"
								:placeholder="__('Default: 20')"
								:model-value="form.max_iterations"
								:disabled="saving"
								:description="__('How many tool-call rounds this agent gets per turn before it stops. Leave blank to use the default.')"
								@update:model-value="(v) => (form.max_iterations = v === '' ? null : Number(v))"
							/>

							<Switch
								v-model="form.enabled"
								:label="__('Enabled')"
								:description="__('Off = this agent is hidden from pickers and won\'t run.')"
								:disabled="saving"
							/>
						</div>
					</DocSection>

					<DocSection :label="__('Instructions')" :collapsible="false">
						<div class="agent-instructions">
							<Textarea
								:rows="12"
								:placeholder="
									__('What should this agent do? Describe its role, scope, and rules.')
								"
								:model-value="form.instructions"
								:disabled="saving"
								@update:model-value="(v) => (form.instructions = v)"
							/>
						</div>
					</DocSection>

					<DocSection :label="__('Tools')" :collapsible="false">
						<div class="flex flex-col gap-2">
							<div v-if="form.tools.length" class="flex items-center gap-2 px-1">
								<span class="flex-1 text-xs text-ink-gray-5">{{ __("Tool") }}</span>
								<span class="w-44 text-xs text-ink-gray-5">{{ __("Permission") }}</span>
								<span class="w-6"></span>
							</div>

							<div
								v-for="(row, index) in form.tools"
								:key="index"
								class="flex items-center gap-2"
							>
								<PanelDropdown
									class="flex-1"
									:items="toolItems"
									:model-value="row.tool"
									:disabled="saving"
									placement="bottom"
									searchable
									match-trigger-width
									@update:model-value="(v) => (row.tool = v)"
								>
									<template #trigger="{ toggle }">
										<button
											class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2"
											@click="toggle"
										>
											<span class="truncate">{{ toolLabel(row.tool) }}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>

								<PanelDropdown
									class="w-44"
									:items="PERMISSION_ITEMS"
									:model-value="row.permission"
									:disabled="saving"
									placement="bottom"
									@update:model-value="(v) => (row.permission = v)"
								>
									<template #trigger="{ toggle }">
										<button
											class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2"
											@click="toggle"
										>
											<span class="truncate">{{ permissionLabel(row.permission) }}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>

								<button
									class="flex h-8 w-6 shrink-0 items-center justify-center rounded-md text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
									:disabled="saving"
									:title="__('Remove tool')"
									@click="removeToolRow(index)"
								>
									<FeatherIcon name="x" class="h-3.5 w-3.5" />
								</button>
							</div>

							<button
								class="flex items-center justify-center gap-1.5 rounded-md border border-dashed border-outline-gray-2 py-2 text-xs text-ink-gray-6 hover:bg-surface-gray-2"
								:disabled="saving"
								@click="addToolRow"
							>
								<FeatherIcon name="plus" class="h-3.5 w-3.5" />
								{{ __("Add Row") }}
							</button>
						</div>
					</DocSection>

					<DocSection :label="__('Knowledge Base')" :collapsible="false">
						<div
							class="flex flex-wrap items-center gap-1.5 rounded-md border border-outline-gray-2 bg-surface-white p-1.5"
						>
							<span
								v-for="kb in form.knowledge_bases"
								:key="kb"
								class="flex items-center gap-1 rounded-md bg-surface-gray-2 px-2 py-1 text-xs font-normal text-ink-gray-8"
							>
								{{ knowledgeBaseLabel(kb) }}
								<button
									class="text-ink-gray-5 hover:text-ink-gray-8"
									:disabled="saving"
									:title="__('Remove')"
									@click="removeKnowledgeBase(kb)"
								>
									<FeatherIcon name="x" class="h-3 w-3" />
								</button>
							</span>

							<PanelDropdown
								:items="availableKnowledgeBaseItems"
								:disabled="saving"
								placement="bottom"
								searchable
								@update:model-value="addKnowledgeBase"
							>
								<template #trigger="{ toggle }">
									<button
										class="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
										@click="toggle"
									>
										<FeatherIcon name="plus" class="h-3.5 w-3.5" />
										{{ __("Add") }}
									</button>
								</template>
							</PanelDropdown>
						</div>
					</DocSection>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
/* Textarea's own size prop only ever emits text-base (15px, per this app's
   Tailwind fontSize scale) — no smaller option — so the 14px ask has to
   override the rendered <textarea> directly. */
.agent-instructions :deep(textarea) {
	font-size: 14px !important;
}

/* Breadcrumbs' crumb links render at text-lg (17px in this app's Tailwind
   fontSize scale) — no smaller size prop exists, so this has to target the
   rendered <a>/<button> tags directly. */
.form-breadcrumbs :deep(a),
.form-breadcrumbs :deep(button) {
	font-size: 15px !important;
}
</style>
