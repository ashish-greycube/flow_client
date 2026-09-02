<script setup>
import { computed } from "vue";
import PanelDropdown from "@/components/PanelDropdown.vue";
import { FeatherIcon } from "@/lib/ui";

const props = defineProps({
	modelValue: { type: [String, Number], default: "" },
	label: { type: String, default: "" },
	type: { type: String, default: "text" },
	options: { type: Array, default: () => [] },
	required: { type: Boolean, default: false },
});
defineEmits(["update:modelValue"]);

const valueOf = (option) => (typeof option === "object" ? option.value : option);
const labelOf = (option) => (typeof option === "object" ? option.label : option);
const dropdownItems = computed(() =>
	props.options.map((option) => ({ value: valueOf(option), label: labelOf(option) })),
);
const selectedLabel = computed(
	() => dropdownItems.value.find((option) => option.value === props.modelValue)?.label || "",
);
</script>

<template>
	<div class="block">
		<span v-if="label" class="mb-1.5 block text-xs font-normal text-ink-gray-7">
			{{ label }}<span v-if="required" class="text-red-500"> *</span>
		</span>
		<textarea
			v-if="type === 'textarea'"
			:value="modelValue"
			rows="3"
			class="w-full resize-y rounded-md border border-outline-gray-2 bg-surface-white px-3 py-2 text-sm font-normal text-ink-gray-9 outline-none focus:border-outline-gray-4 focus:ring-1 focus:ring-outline-gray-3"
			@input="$emit('update:modelValue', $event.target.value)"
		></textarea>
		<PanelDropdown
			v-else-if="type === 'select'"
			:model-value="modelValue"
			:items="dropdownItems"
			placement="bottom"
			searchable
			match-trigger-width
			hide-scrollbar
			@update:model-value="$emit('update:modelValue', $event)"
		>
			<template #trigger="{ toggle, open }">
				<button
					type="button"
					class="flex h-9 w-full items-center gap-2 rounded-md border border-outline-gray-2 bg-surface-white px-3 text-left text-sm font-normal text-ink-gray-9 outline-none hover:border-outline-gray-3 focus:border-outline-gray-4 focus:ring-1 focus:ring-outline-gray-3"
					:aria-expanded="open"
					@click="toggle"
				>
					<span class="min-w-0 flex-1 truncate">{{ selectedLabel }}</span>
					<FeatherIcon
						name="chevron-down"
						class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
					/>
				</button>
			</template>
		</PanelDropdown>
		<input
			v-else
			:value="modelValue"
			:type="type"
			class="h-9 w-full rounded-md border border-outline-gray-2 bg-surface-white px-3 text-sm font-normal text-ink-gray-9 outline-none focus:border-outline-gray-4 focus:ring-1 focus:ring-outline-gray-3"
			@input="$emit('update:modelValue', $event.target.value)"
		/>
	</div>
</template>
