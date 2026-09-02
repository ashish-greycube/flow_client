<template>
	<div class="border-t border-outline-gray-1 py-4 first:border-t-0">
		<div
			class="flex h-8 max-w-fit items-center gap-1.5"
			:class="{ 'cursor-pointer': collapsible }"
			@click="collapsible && toggle()"
		>
			<FeatherIcon
				v-if="collapsible"
				name="chevron-right"
				class="h-4 w-4 text-ink-gray-9 transition-transform duration-300 ease-in-out"
				:class="{ 'rotate-90': isOpened }"
			/>
			<span class="text-base font-semibold text-ink-gray-9">{{ label }}</span>
			<slot name="header-suffix" />
		</div>
		<div v-show="isOpened" class="pt-2">
			<slot />
		</div>
	</div>
</template>

<script setup>
// Ported from Jarvis's DocSection (frontend/src/components/doc/DocSection.vue):
// bold section label, chevron toggle, border-t between sections — the same
// visual grouping the Macro new/edit page uses for its "Details" block.
import { ref } from "vue";
import { FeatherIcon } from "@/lib/ui";

const props = defineProps({
	label: { type: String, default: "" },
	opened: { type: Boolean, default: true },
	collapsible: { type: Boolean, default: true },
});

const isOpened = ref(props.opened);

function toggle() {
	isOpened.value = !isOpened.value;
}
</script>
