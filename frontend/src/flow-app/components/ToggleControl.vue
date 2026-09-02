<script setup>
defineProps({
	modelValue: { type: Boolean, default: false },
	label: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>

<template>
	<label class="flex cursor-pointer items-center gap-2 text-sm font-normal text-ink-gray-8">
		<input
			type="checkbox"
			class="peer sr-only"
			:checked="modelValue"
			@change="$emit('update:modelValue', $event.target.checked)"
		/>
		<span
			class="relative h-5 w-9 shrink-0 rounded-full transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-outline-gray-3"
			:class="modelValue ? 'bg-surface-gray-6' : 'bg-surface-gray-4'"
		>
			<span
				class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
				:class="modelValue ? 'translate-x-4' : 'translate-x-0'"
			></span>
		</span>
		<span v-if="label">{{ label }}</span>
	</label>
</template>
