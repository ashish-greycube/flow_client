<script setup>
import { ref, computed, watch } from "vue";
import { Button, FeatherIcon } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { startBatch, FILE2ERP_DOCUMENT_TYPES, COMBINABLE_DOCUMENT_TYPES } from "@/api/file2erp";

// Shown after several files are uploaded together: what they are, and whether they
// become one document or one each. A plain fixed-overlay modal (never teleported) — same
// reason as SaveAsMacroDialog: it has to stay inside #flow-root to pick up the page's
// scoped styles. "Decide later" just closes it, leaving each file to be set up on its own
// page as before.
const props = defineProps({
	modelValue: { type: Boolean, default: false },
	// The just-created File2ERP entries.
	entries: { type: Array, default: () => [] },
	defaultType: { type: String, default: "Expense Claim" },
});
const emit = defineEmits(["update:modelValue", "started"]);

const documentType = ref(props.defaultType);
const mode = ref("separate");
const starting = ref(false);

const canCombine = computed(() => COMBINABLE_DOCUMENT_TYPES.includes(documentType.value));

watch(
	() => props.modelValue,
	(open) => {
		if (!open) return;
		documentType.value = props.defaultType;
		mode.value = canCombine.value ? "combined" : "separate";
	},
);
watch(canCombine, (allowed) => {
	if (!allowed) mode.value = "separate";
});

function close() {
	if (!starting.value) emit("update:modelValue", false);
}

async function start() {
	starting.value = true;
	try {
		const result = await startBatch(
			props.entries.map((e) => e.name),
			documentType.value,
			mode.value,
		);
		emit("started", { ...result, mode: mode.value, documentType: documentType.value });
		emit("update:modelValue", false);
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not start extraction."), indicator: "red" });
	} finally {
		starting.value = false;
	}
}
</script>

<template>
	<template v-if="modelValue">
		<div class="fixed inset-0 z-40 bg-black/40" @click="close"></div>
		<div
			class="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[30rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-2xl"
		>
			<header class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
				<div>
					<div class="text-sm font-semibold text-ink-gray-9">
						{{ __("{0} files uploaded", [entries.length]) }}
					</div>
					<div class="text-xs text-ink-gray-5">{{ __("Choose what to create from them") }}</div>
				</div>
				<button
					class="flex h-6 w-6 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
					:title="__('Close')"
					@click="close"
				>
					<FeatherIcon name="x" class="h-3.5 w-3.5" />
				</button>
			</header>

			<div class="flow-scrollbar flex flex-col gap-4 overflow-y-auto px-4 py-4">
				<div class="flex flex-col gap-1.5">
					<label class="text-xs font-medium text-ink-gray-6">{{ __("Document Type") }}</label>
					<select
						v-model="documentType"
						class="h-8 w-full rounded border border-outline-gray-2 bg-surface-white px-2 text-sm text-ink-gray-8 outline-none focus:border-outline-gray-4"
					>
						<option v-for="opt in FILE2ERP_DOCUMENT_TYPES" :key="opt" :value="opt">{{ opt }}</option>
					</select>
				</div>

				<div class="flex flex-col gap-2">
					<label
						class="flex items-start gap-2 rounded-lg border p-3"
						:class="[
							mode === 'combined' ? 'border-outline-gray-4' : 'border-outline-gray-1',
							canCombine ? 'cursor-pointer' : 'cursor-not-allowed opacity-60',
						]"
					>
						<input v-model="mode" type="radio" value="combined" :disabled="!canCombine" class="mt-0.5" />
						<span>
							<span class="block text-sm font-medium text-ink-gray-8">
								{{ __("One {0} for all {1} files", [documentType, entries.length]) }}
							</span>
							<span class="block text-xs text-ink-gray-5">
								{{
									canCombine
										? __("Every receipt becomes a row of one claim, reviewed together on one page.")
										: __("Only available for Expense Claims.")
								}}
							</span>
						</span>
					</label>
					<label
						class="flex cursor-pointer items-start gap-2 rounded-lg border p-3"
						:class="mode === 'separate' ? 'border-outline-gray-4' : 'border-outline-gray-1'"
					>
						<input v-model="mode" type="radio" value="separate" class="mt-0.5" />
						<span>
							<span class="block text-sm font-medium text-ink-gray-8">
								{{ __("A separate {0} for each file", [documentType]) }}
							</span>
							<span class="block text-xs text-ink-gray-5">
								{{ __("Each file is read now and reviewed on its own page.") }}
							</span>
						</span>
					</label>
				</div>
			</div>

			<footer class="flex items-center justify-between border-t border-outline-gray-1 px-4 py-3">
				<Button variant="ghost" :disabled="starting" @click="close">{{ __("Decide later") }}</Button>
				<Button variant="solid" :loading="starting" @click="start">{{ __("Extract Data") }}</Button>
			</footer>
		</div>
	</template>
</template>
