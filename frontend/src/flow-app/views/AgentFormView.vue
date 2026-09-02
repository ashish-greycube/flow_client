<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import PanelDropdown from "@/components/PanelDropdown.vue";
import { Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadModels, getAgent, createAgent, updateAgent, renameAgent } from "@/api/client";

// Full page for both Create and Edit (routed at /agents/new and
// /agents/:name) — a dialog previously covered this, but a page keeps the
// sidebar visible and gives each agent its own real, bookmarkable URL.
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

const modelItems = computed(() => models.value.map((m) => ({ value: m.name, label: m.title })));
const canSave = computed(
	() => form.title.trim() && form.model && form.instructions.trim() && !saving.value
);

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
		} finally {
			loading.value = false;
		}
	} else {
		form.title = "";
		form.model = models.value[0]?.name || null;
		form.instructions = "";
		form.enabled = true;
	}
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
			<div class="flex items-center gap-2">
				<button
					class="flex h-7 w-7 items-center justify-center rounded-md text-ink-gray-6 hover:bg-surface-gray-2"
					:title="__('Back to Agents')"
					@click="goBack"
				>
					<FeatherIcon name="arrow-left" class="h-4 w-4" />
				</button>
				<h1 class="text-lg font-normal text-ink-gray-9">
					{{ isEdit ? __("Edit Agent") : __("New Agent") }}
				</h1>
			</div>
			<div class="flex items-center gap-2">
				<Button variant="subtle" :disabled="saving" @click="goBack">{{ __("Cancel") }}</Button>
				<Button variant="solid" :disabled="!canSave" :loading="saving" @click="save">{{
					isEdit ? __("Save") : __("Create Agent")
				}}</Button>
			</div>
		</header>

		<div v-if="loading" class="flex justify-center py-16">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>

		<div v-else class="flow-scrollbar flex-1 overflow-y-auto px-6 py-6">
			<div class="mx-auto flex max-w-3xl flex-col gap-4">
				<div>
					<label class="mb-1 block text-xs text-ink-gray-6">{{ __("Title") }}</label>
					<input
						v-model="form.title"
						type="text"
						:disabled="isSystemGenerated"
						:placeholder="__('e.g. Sales Analysis Agent')"
						class="h-8 w-full rounded-md border border-outline-gray-2 bg-surface-white px-2.5 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3 disabled:bg-surface-gray-1 disabled:text-ink-gray-5"
					/>
					<p v-if="isSystemGenerated" class="mt-1 text-xs text-ink-gray-5">
						{{ __("Built-in agents can't be renamed.") }}
					</p>
				</div>

				<div>
					<label class="mb-1 block text-xs text-ink-gray-6">{{ __("Model") }}</label>
					<PanelDropdown
						:items="modelItems"
						:model-value="form.model"
						placement="bottom"
						searchable
						@update:model-value="(v) => (form.model = v)"
					>
						<template #trigger="{ toggle }">
							<button
								class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm text-ink-gray-9 hover:bg-surface-gray-2"
								@click="toggle"
							>
								<span class="truncate">{{
									modelItems.find((m) => m.value === form.model)?.label ||
									__("Select a model")
								}}</span>
								<FeatherIcon name="chevron-down" class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" />
							</button>
						</template>
					</PanelDropdown>
				</div>

				<div>
					<label class="mb-1 block text-xs text-ink-gray-6">{{ __("Instructions") }}</label>
					<textarea
						v-model="form.instructions"
						rows="12"
						:placeholder="__('What should this agent do? Describe its role, scope, and rules.')"
						class="w-full resize-none rounded-md border border-outline-gray-2 bg-surface-white px-2.5 py-2 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3"
					></textarea>
				</div>

				<label class="flex items-center gap-2 text-sm text-ink-gray-8">
					<input v-model="form.enabled" type="checkbox" class="h-3.5 w-3.5" />
					{{ __("Enabled") }}
				</label>
			</div>
		</div>
	</div>
</template>
