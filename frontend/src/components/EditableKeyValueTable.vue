<script setup>
// Editable {field: value} grid, e.g. a File2ERP entry's parent-level extracted_fields.
// Both columns are plain editable inputs on every row — "Add Field" pushes a new row
// straight into the table (focusing its Field cell) rather than opening a separate form.
//
// `modelValue` seeds the rows but isn't watched continuously — every keystroke here
// emits an update, and re-deriving rows from that echoed-back prop on every change
// would reset mid-edit input (and lose focus). `resetKey` is the explicit signal for
// "load a genuinely different document" (e.g. the parent passes the File2ERP entry's
// name + modified) — only then are rows re-seeded from modelValue.
import { nextTick, ref, watch } from "vue";
import { FeatherIcon } from "@/lib/ui";
import { __ } from "@/lib/translate";

const props = defineProps({
	modelValue: { type: Object, default: () => ({}) },
	resetKey: { type: [String, Number], default: "" },
	disabled: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue"]);

let uid = 0;
function toRows(obj) {
	return Object.entries(obj || {}).map(([key, value]) => ({ id: ++uid, key, value: value ?? "" }));
}

const rows = ref(toRows(props.modelValue));
// Plain (non-reactive) DOM-node map, just to focus a newly added row's Field input —
// not app state, so it doesn't need to be a ref.
const keyInputs = {};

watch(
	() => props.resetKey,
	() => {
		rows.value = toRows(props.modelValue);
	},
);

watch(
	rows,
	() => {
		const out = {};
		for (const row of rows.value) {
			const key = (row.key || "").trim();
			if (key) out[key] = row.value;
		}
		emit("update:modelValue", out);
	},
	{ deep: true },
);

async function addRow() {
	const row = { id: ++uid, key: "", value: "" };
	rows.value.push(row);
	await nextTick();
	keyInputs[row.id]?.focus();
}

function removeRow(id) {
	rows.value = rows.value.filter((r) => r.id !== id);
	delete keyInputs[id];
}
</script>

<template>
	<div class="overflow-hidden rounded-lg border border-outline-gray-1">
		<div v-if="!rows.length" class="px-3 py-6 text-center text-sm text-ink-gray-5">
			{{ __("No fields extracted.") }}
		</div>
		<div
			v-for="row in rows"
			:key="row.id"
			class="group flex items-center gap-2 border-b border-outline-gray-1 px-3 py-1.5 last:border-0 hover:bg-surface-gray-1"
		>
			<input
				:ref="(el) => { if (el) keyInputs[row.id] = el; }"
				v-model="row.key"
				:disabled="disabled"
				:placeholder="__('Field')"
				class="w-2/5 min-w-0 shrink-0 rounded border-0 bg-transparent px-1.5 py-1 text-sm text-ink-gray-6 outline-none focus:bg-surface-gray-2 disabled:text-ink-gray-6"
			/>
			<input
				v-model="row.value"
				:disabled="disabled"
				:placeholder="__('Value')"
				class="min-w-0 flex-1 rounded border-0 bg-transparent px-1.5 py-1 text-sm text-ink-gray-9 outline-none focus:bg-surface-gray-2 disabled:text-ink-gray-6"
			/>
			<button
				v-if="!disabled"
				class="flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink-gray-4 opacity-0 hover:bg-surface-gray-2 hover:text-ink-red-4 group-hover:opacity-100"
				:title="__('Remove')"
				@click="removeRow(row.id)"
			>
				<FeatherIcon name="trash-2" class="h-3.5 w-3.5" />
			</button>
		</div>

		<button
			v-if="!disabled"
			class="flex w-full items-center gap-1.5 border-t border-outline-gray-1 px-3 py-2 text-sm text-ink-gray-6 hover:bg-surface-gray-1"
			@click="addRow"
		>
			<FeatherIcon name="plus" class="h-3.5 w-3.5" />
			{{ __("Add Field") }}
		</button>
	</div>
</template>
