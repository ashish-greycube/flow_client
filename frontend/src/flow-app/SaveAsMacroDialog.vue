<script setup>
import { ref, computed, watch, nextTick } from "vue";
import { Button, FeatherIcon, TextInput } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { createMacroFromPrompts } from "@/api/client";

// A plain fixed-overlay modal (never teleported) — same reason as
// ToolPermissionsDialog: it has to stay inside #flow-root to pick up the
// page's scoped styles.
const props = defineProps({
	modelValue: { type: Boolean, default: false },
	agent: { type: String, default: null },
	agentLabel: { type: String, default: "" },
	// [{ label, prompt }, ...] — the conversation's user prompts, in order.
	steps: { type: Array, default: () => [] },
	defaultName: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const name = ref("");
const saving = ref(false);
const nameInput = ref(null);

watch(
	() => props.modelValue,
	(open) => {
		if (!open) return;
		name.value = props.defaultName || "";
		nextTick(() => nameInput.value?.el?.focus());
	}
);

const canSave = computed(() => name.value.trim() && props.steps.length && !saving.value);

function close() {
	if (saving.value) return;
	emit("update:modelValue", false);
}

async function save() {
	if (!canSave.value) return;
	saving.value = true;
	try {
		const macroName = name.value.trim();
		await createMacroFromPrompts(
			props.agent,
			macroName,
			props.steps
		);
		emit("update:modelValue", false);
		frappe.show_alert({
			message: __("Macro {0} created.", [macroName]),
			indicator: "green",
		});
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Could not create macro."), indicator: "red" });
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<template v-if="modelValue">
		<div class="fixed inset-0 z-40 bg-black/40" @click="close"></div>
		<div
			class="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[32rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-2xl"
		>
			<header class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
				<div>
					<div class="text-sm font-semibold text-ink-gray-9">{{ __("Save as Macro") }}</div>
					<div class="text-xs text-ink-gray-5">
						{{ __("Reuse these prompts on demand") }}
					</div>
				</div>
				<button
					class="flex h-6 w-6 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
					:title="__('Close')"
					@click="close"
				>
					<FeatherIcon name="x" class="h-3.5 w-3.5" />
				</button>
			</header>

			<div class="flex flex-col gap-3 overflow-y-auto px-4 py-4 flow-scrollbar">
				<TextInput
					ref="nameInput"
					type="text"
					:label="__('Macro name')"
					:model-value="name"
					:placeholder="__('e.g. Weekly overdue invoice check')"
					@update:model-value="(v) => (name = v)"
					@keydown.enter="save"
				/>

				<div v-if="agentLabel" class="text-xs text-ink-gray-5">
					{{ __("Runs through the {0} agent", [agentLabel]) }}
				</div>

				<div>
					<div class="mb-1.5 text-xs font-medium text-ink-gray-6">
						{{
							steps.length === 1
								? __("1 step from this conversation")
								: __("{0} steps from this conversation", [steps.length])
						}}
					</div>
					<ol class="flex flex-col gap-1 rounded-lg border border-outline-gray-1 p-2">
						<li
							v-for="(step, i) in steps"
							:key="i"
							class="flex gap-2 rounded-md px-1.5 py-1 text-sm text-ink-gray-8"
						>
							<span class="shrink-0 text-ink-gray-4">{{ i + 1 }}.</span>
							<span class="line-clamp-2">{{ step.prompt }}</span>
						</li>
					</ol>
				</div>
			</div>

			<footer class="flex justify-end gap-2 border-t border-outline-gray-1 px-4 py-3">
				<Button variant="subtle" :disabled="saving" @click="close">{{ __("Cancel") }}</Button>
				<Button variant="solid" :disabled="!canSave" :loading="saving" @click="save">{{
					__("Create Macro")
				}}</Button>
			</footer>
		</div>
	</template>
</template>
