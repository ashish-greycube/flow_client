<script setup>
// Editable line-items grid, e.g. a File2ERP entry's extracted_line_items. Columns are
// inferred from the union of keys across all rows (documents vary — an invoice's
// columns aren't a receipt's), rendered as a plain table with humanized headers —
// generic until the data is mapped onto an actual target DocType.
//
// Same resetKey convention as EditableKeyValueTable: modelValue seeds state once, and
// is re-applied only when resetKey changes (a genuinely different document loaded) —
// not on every self-triggered emit, which would otherwise reset mid-edit input.
import { ref, watch } from "vue";
import { Button, FeatherIcon, TextInput } from "@/lib/ui";
import { __ } from "@/lib/translate";

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	resetKey: { type: [String, Number], default: "" },
	disabled: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue"]);

let rowUid = 0;

function deriveColumns(items) {
	const columns = [];
	for (const item of items || []) {
		for (const key of Object.keys(item || {})) {
			if (!columns.includes(key)) columns.push(key);
		}
	}
	return columns;
}

function toState(items) {
	return {
		columns: deriveColumns(items),
		rows: (items || []).map((item) => ({ id: ++rowUid, cells: { ...item } })),
	};
}

const state = ref(toState(props.modelValue));
const addingColumn = ref(false);
const newColumnLabel = ref("");

watch(
	() => props.resetKey,
	() => {
		state.value = toState(props.modelValue);
	},
);

watch(
	state,
	() => {
		const out = state.value.rows.map((row) => {
			const obj = {};
			for (const col of state.value.columns) obj[col] = row.cells[col] ?? "";
			return obj;
		});
		emit("update:modelValue", out);
	},
	{ deep: true },
);

function humanize(key) {
	return (key || "")
		.replace(/[_-]+/g, " ")
		.trim()
		.replace(/\b\w/g, (c) => c.toUpperCase());
}

function slugify(label) {
	return label
		.trim()
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "_")
		.replace(/^_+|_+$/g, "");
}

function addRow() {
	const cells = {};
	for (const col of state.value.columns) cells[col] = "";
	state.value.rows.push({ id: ++rowUid, cells });
}

function removeRow(id) {
	state.value.rows = state.value.rows.filter((r) => r.id !== id);
}

function startAddColumn() {
	addingColumn.value = true;
	newColumnLabel.value = "";
}

function cancelAddColumn() {
	addingColumn.value = false;
}

function confirmAddColumn() {
	const col = slugify(newColumnLabel.value);
	if (!col || state.value.columns.includes(col)) return;
	state.value.columns.push(col);
	for (const row of state.value.rows) row.cells[col] = "";
	addingColumn.value = false;
}

function removeColumn(col) {
	state.value.columns = state.value.columns.filter((c) => c !== col);
	for (const row of state.value.rows) delete row.cells[col];
}
</script>

<template>
	<div class="overflow-hidden rounded-lg border border-outline-gray-1">
		<div
			v-if="!state.rows.length && !state.columns.length"
			class="px-3 py-6 text-center text-sm text-ink-gray-5"
		>
			{{ __("No line items extracted.") }}
		</div>

		<div v-else class="overflow-x-auto">
			<table class="w-full min-w-max border-collapse text-sm">
				<thead>
					<tr class="border-b border-outline-gray-1 bg-surface-gray-1">
						<th
							v-for="col in state.columns"
							:key="col"
							class="group whitespace-nowrap px-3 py-2 text-left text-xs font-medium text-ink-gray-6"
						>
							<span class="inline-flex items-center gap-1">
								{{ humanize(col) }}
								<button
									v-if="!disabled"
									class="hidden h-4 w-4 items-center justify-center rounded text-ink-gray-4 hover:bg-surface-gray-3 hover:text-ink-red-4 group-hover:inline-flex"
									:title="__('Remove column')"
									@click="removeColumn(col)"
								>
									<FeatherIcon name="x" class="h-3 w-3" />
								</button>
							</span>
						</th>
						<th v-if="!disabled" class="w-8"></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in state.rows"
						:key="row.id"
						class="group border-b border-outline-gray-1 last:border-0 hover:bg-surface-gray-1"
					>
						<td v-for="col in state.columns" :key="col" class="px-1 py-1">
							<input
								v-model="row.cells[col]"
								:disabled="disabled"
								class="w-full min-w-[8ch] rounded border-0 bg-transparent px-1.5 py-1 text-sm text-ink-gray-9 outline-none focus:bg-surface-white disabled:text-ink-gray-6"
							/>
						</td>
						<td v-if="!disabled" class="px-1">
							<button
								class="flex h-6 w-6 items-center justify-center rounded text-ink-gray-4 opacity-0 hover:bg-surface-gray-2 hover:text-ink-red-4 group-hover:opacity-100"
								:title="__('Remove row')"
								@click="removeRow(row.id)"
							>
								<FeatherIcon name="trash-2" class="h-3.5 w-3.5" />
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-if="!disabled" class="flex flex-wrap items-center gap-2 border-t border-outline-gray-1 px-3 py-2">
			<button
				class="flex items-center gap-1.5 text-sm text-ink-gray-6 hover:text-ink-gray-8 disabled:cursor-default disabled:opacity-40"
				:disabled="!state.columns.length"
				@click="addRow"
			>
				<FeatherIcon name="plus" class="h-3.5 w-3.5" />
				{{ __("Add Row") }}
			</button>
			<span class="text-ink-gray-3">·</span>
			<template v-if="addingColumn">
				<TextInput
					v-model="newColumnLabel"
					:placeholder="__('Column name')"
					class="w-40"
					autofocus
					@keydown.enter="confirmAddColumn"
					@keydown.escape="cancelAddColumn"
				/>
				<Button variant="solid" @click="confirmAddColumn">{{ __("Add") }}</Button>
				<Button variant="outline" @click="cancelAddColumn">{{ __("Cancel") }}</Button>
			</template>
			<button
				v-else
				class="flex items-center gap-1.5 text-sm text-ink-gray-6 hover:text-ink-gray-8"
				@click="startAddColumn"
			>
				<FeatherIcon name="plus" class="h-3.5 w-3.5" />
				{{ __("Add Column") }}
			</button>
		</div>
	</div>
</template>
