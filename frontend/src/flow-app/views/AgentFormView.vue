<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import PanelDropdown from "@/components/PanelDropdown.vue";
import DocSection from "@/components/DocSection.vue";
import { Button, FeatherIcon, Spinner, Badge, TextInput, Textarea, Switch, Breadcrumbs } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadModels, getAgent, createAgent, updateAgent, renameAgent } from "@/api/client";

// Full page for both Create and Edit (routed at /agents/new and
// /agents/:name) — a dialog previously covered this, but a page keeps the
// sidebar visible and gives each agent its own real, bookmarkable URL.
// Styled after Jarvis's Macro new/edit page (frontend/src/pages/macros/
// MacroDetail.vue): breadcrumbs + actions header, a title row with a "Not
// Saved" badge, and fields grouped under a "Details" section.
const route = useRoute();
const router = useRouter();

const agentName = computed(() => route.params.name || null);
const isEdit = computed(() => !!agentName.value);

const loading = ref(false);
const saving = ref(false);
const models = ref([]);
// Flow Agent is `autoname: "field:title"` — the title field is locked in
// sync with the docname (Document._sync_autoname_field reverts any other
// change to it on save), and renames are blocked outright for built-in
// agents (flow_agent.py's before_rename). Title is only actually editable
// when neither of those applies.
const isSystemGenerated = ref(false);

const form = reactive({
	title: "",
	model: null,
	instructions: "",
	enabled: true,
});
// Saved-state copy for the dirty compare, set once load() settles.
const snapshot = ref(null);

const modelItems = computed(() => models.value.map((m) => ({ value: m.name, label: m.title })));
const canSave = computed(
	() => form.title.trim() && form.model && form.instructions.trim() && !saving.value
);

const dirty = computed(() => {
	const snap = snapshot.value;
	if (!snap || loading.value) return false;
	return (
		(form.title || "") !== snap.title ||
		(form.model || null) !== snap.model ||
		(form.instructions || "") !== snap.instructions ||
		(form.enabled ? 1 : 0) !== snap.enabled
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
		instructions: form.instructions,
		enabled: form.enabled ? 1 : 0,
	};
}

async function load() {
	models.value = await loadModels().catch(() => []);

	if (isEdit.value) {
		loading.value = true;
		try {
			const doc = await getAgent(agentName.value);
			form.title = doc.title || "";
			form.model = doc.model || null;
			form.instructions = doc.instructions || "";
			form.enabled = !!doc.enabled;
			isSystemGenerated.value = !!doc.is_system_generated;
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
		form.instructions = "";
		form.enabled = true;
	}
	snapshotForm();
}
onMounted(load);

function goBack() {
	router.push({ name: "agents" });
}

async function save() {
	if (!canSave.value) return;
	saving.value = true;
	try {
		const values = {
			model: form.model,
			instructions: form.instructions.trim(),
			enabled: form.enabled ? 1 : 0,
		};
		if (isEdit.value) {
			// Title first, and separately: renaming changes the docname, so the
			// field update below must target whatever name comes back from it,
			// not the (possibly now-stale) agentName.
			let name = agentName.value;
			const newTitle = form.title.trim();
			if (!isSystemGenerated.value && newTitle !== name) {
				name = await renameAgent(name, newTitle);
			}
			await updateAgent(name, values);
			frappe.show_alert({ message: __("Agent updated."), indicator: "green" });
		} else {
			await createAgent({ title: form.title.trim(), ...values });
			frappe.show_alert({ message: __("Agent created."), indicator: "green" });
		}
		goBack();
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
			<Breadcrumbs :items="breadcrumbs" />
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

							<div class="agent-instructions">
								<Textarea
									:label="__('Instructions')"
									:rows="12"
									:placeholder="
										__('What should this agent do? Describe its role, scope, and rules.')
									"
									:model-value="form.instructions"
									:disabled="saving"
									@update:model-value="(v) => (form.instructions = v)"
								/>
							</div>

							<Switch
								v-model="form.enabled"
								:label="__('Enabled')"
								:description="__('Off = this agent is hidden from pickers and won\'t run.')"
								:disabled="saving"
							/>
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
</style>
