<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DocSection from "@/components/DocSection.vue";
import {
	Button,
	FeatherIcon,
	Spinner,
	Badge,
	TextInput,
	Textarea,
	Switch,
	Combobox,
	Breadcrumbs,
} from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadTools, getSkill, createSkill, saveSkill } from "@/api/client";
import { useStore } from "@/store";

const route = useRoute();
const router = useRouter();
const { refreshSkills } = useStore();

const skillName = computed(() => route.params.name || null);
const isEdit = computed(() => !!skillName.value);
const canCreate = (frappe.boot.user?.can_create || []).includes("Flow Skill");
const canWrite = (frappe.boot.user?.can_write || []).includes("Flow Skill");
const readOnly = computed(() => (isEdit.value ? !canWrite : !canCreate));

const loading = ref(false);
const saving = ref(false);
const tools = ref([]);
const isSystemGenerated = ref(false);
const docMeta = ref({ modified: null, creation: null, owner: null });
const snapshot = ref(null);
const form = reactive({
	title: "",
	command: "",
	description: "",
	instructions: "",
	enabled: true,
	tools: [],
});

const toolItems = computed(() =>
	tools.value
		.filter((tool) => !form.tools.includes(tool.name))
		.map((tool) => ({ value: tool.name, label: tool.title })),
);
const canSave = computed(
	() =>
		!readOnly.value &&
		form.title.trim() &&
		form.command.trim() &&
		form.description.trim() &&
		form.instructions.trim() &&
		!saving.value,
);
const dirty = computed(() => {
	if (!snapshot.value || loading.value) return false;
	return JSON.stringify(formState()) !== JSON.stringify(snapshot.value);
});
const pageTitle = computed(() =>
	isEdit.value ? form.title || skillName.value : form.title || __("New Skill"),
);
const breadcrumbs = computed(() => [
	{ label: __("Skills"), route: { name: "skills" } },
	isEdit.value
		? {
				label: pageTitle.value,
				route: { name: "skill-edit", params: { name: skillName.value } },
			}
		: { label: __("New Skill"), route: { name: "skill-new" } },
]);

function formState() {
	return {
		title: form.title,
		command: form.command,
		description: form.description,
		instructions: form.instructions,
		enabled: form.enabled ? 1 : 0,
		tools: [...form.tools].sort(),
	};
}

function normalizeCommand(value) {
	return (value || "")
		.trim()
		.replace(/^\/+/, "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "");
}

function addTool(name) {
	if (name && !form.tools.includes(name)) form.tools.push(name);
}

function removeTool(name) {
	form.tools = form.tools.filter((tool) => tool !== name);
}

function toolLabel(name) {
	return tools.value.find((tool) => tool.name === name)?.title || name;
}

async function load() {
	tools.value = await loadTools().catch(() => []);
	if (isEdit.value) {
		loading.value = true;
		try {
			const doc = await getSkill(skillName.value);
			form.title = doc.title || "";
			form.command = doc.command || "";
			form.description = doc.description || "";
			form.instructions = doc.instructions || "";
			form.enabled = !!doc.enabled;
			form.tools = (doc.tools || []).map((row) => row.tool);
			isSystemGenerated.value = !!doc.is_system_generated;
			docMeta.value = { modified: doc.modified, creation: doc.creation, owner: doc.owner };
		} catch (error) {
			frappe.show_alert({
				message: error.message || __("Could not load skill."),
				indicator: "red",
			});
			goBack();
			return;
		} finally {
			loading.value = false;
		}
	} else {
		form.title = "";
		form.command = "";
		form.description = "";
		form.instructions = "";
		form.enabled = true;
		form.tools = [];
		isSystemGenerated.value = false;
	}
	snapshot.value = formState();
}

watch(skillName, load, { immediate: true });

function goBack() {
	router.push({ name: "skills" });
}

async function save() {
	if (!canSave.value) return;
	saving.value = true;
	try {
		const values = {
			title: form.title.trim(),
			command: normalizeCommand(form.command),
			description: form.description.trim(),
			instructions: form.instructions.trim(),
			enabled: form.enabled ? 1 : 0,
			tools: form.tools.map((tool) => ({ tool })),
		};
		let name = skillName.value;
		if (isEdit.value) {
			await saveSkill({
				name,
				...docMeta.value,
				is_system_generated: isSystemGenerated.value ? 1 : 0,
				...values,
			});
			frappe.show_alert({ message: __("Skill updated."), indicator: "green" });
		} else {
			const created = await createSkill(values);
			name = created.name;
			frappe.show_alert({ message: __("Skill created."), indicator: "green" });
		}
		await refreshSkills();
		if (skillName.value !== name) {
			await router.replace({ name: "skill-edit", params: { name } });
		} else {
			await load();
		}
	} catch (error) {
		frappe.show_alert({
			message: error.message || __("Could not save skill."),
			indicator: "red",
		});
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<div
		class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9"
	>
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<Breadcrumbs class="form-breadcrumbs" :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<Button variant="subtle" :disabled="saving" @click="goBack">{{
					__("Cancel")
				}}</Button>
				<Button
					v-if="!readOnly"
					variant="solid"
					:disabled="!canSave || !dirty"
					:loading="saving"
					@click="save"
				>
					{{ isEdit ? __("Save") : __("Create Skill") }}
				</Button>
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
					<Badge
						v-if="readOnly"
						variant="subtle"
						theme="gray"
						:label="__('Read only')"
					/>
				</div>

				<div class="mt-4">
					<DocSection :label="__('Details')" :collapsible="false">
						<div class="space-y-4">
							<TextInput
								:label="__('Title')"
								:placeholder="__('e.g. Create Sales Invoice')"
								:model-value="form.title"
								:disabled="readOnly"
								@update:model-value="(value) => (form.title = value)"
							/>
							<TextInput
								:label="__('Command')"
								:placeholder="__('create-sales-invoice')"
								:model-value="form.command"
								:disabled="isEdit || readOnly"
								:description="
									isEdit
										? __('Commands cannot be changed after creation.')
										: __('Enter the command without /.')
								"
								@update:model-value="
									(value) => (form.command = normalizeCommand(value))
								"
							/>
							<Textarea
								:label="__('Description')"
								:rows="3"
								:placeholder="__('Explain when this skill should be used.')"
								:model-value="form.description"
								:disabled="readOnly"
								@update:model-value="(value) => (form.description = value)"
							/>
							<Switch
								v-model="form.enabled"
								:label="__('Enabled')"
								:description="
									__('Disabled skills are hidden from the chat composer.')
								"
								:disabled="readOnly"
							/>
						</div>
					</DocSection>

					<DocSection :label="__('Instructions')" :collapsible="false">
						<Textarea
							class="skill-instructions"
							:label="__('Focused instructions')"
							:rows="12"
							:placeholder="
								__(
									'Describe the workflow, required information, validation, and stopping conditions.',
								)
							"
							:model-value="form.instructions"
							:disabled="readOnly"
							@update:model-value="(value) => (form.instructions = value)"
						/>
					</DocSection>

					<DocSection :label="__('Required Tools')" :collapsible="false">
						<div class="space-y-3">
							<p class="text-sm leading-relaxed text-ink-gray-6">
								{{
									__(
										"The Auto-routed or manually selected agent must provide every tool listed here.",
									)
								}}
							</p>
							<div
								class="flex min-h-10 flex-wrap items-center gap-1.5 rounded-md border border-outline-gray-2 p-1.5"
							>
								<Badge
									v-for="tool in form.tools"
									:key="tool"
									variant="subtle"
									theme="gray"
								>
									{{ toolLabel(tool) }}
									<template v-if="!readOnly" #suffix>
										<Button
											variant="ghost"
											size="xs"
											icon="x"
											:title="__('Remove')"
											@click="removeTool(tool)"
										/>
									</template>
								</Badge>
								<Combobox
									v-if="!readOnly"
									trigger="button"
									:options="toolItems"
									portal-to="#flow-root"
									@update:model-value="addTool"
								>
									<template #trigger="{ toggleOpen }">
										<button
											class="flex items-center gap-1 rounded px-1.5 py-1 text-xs text-ink-gray-6 hover:bg-surface-gray-2"
											@click="toggleOpen"
										>
											<FeatherIcon name="plus" class="h-3.5 w-3.5" />
											{{ __("Add tool") }}
										</button>
									</template>
								</Combobox>
							</div>
						</div>
					</DocSection>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
.skill-instructions :deep(textarea) {
	font-size: 14px !important;
}

.form-breadcrumbs :deep(a),
.form-breadcrumbs :deep(button) {
	font-size: 15px !important;
}
</style>
