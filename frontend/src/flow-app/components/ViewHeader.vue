<script setup>
import { FeatherIcon } from "@/lib/ui";

defineProps({
	title: { type: String, required: true },
	back: { type: Boolean, default: false },
});
defineEmits(["back"]);
</script>

<template>
	<header
		class="flex min-h-16 items-center justify-between border-b border-outline-gray-1 px-6 py-3"
	>
		<div class="flex min-w-0 items-center gap-2">
			<button
				v-if="back"
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded hover:bg-surface-gray-2"
				@click="$emit('back')"
			>
				<FeatherIcon name="arrow-left" class="h-4 w-4" />
			</button>
			<div class="min-w-0">
				<h1 class="truncate text-lg font-medium text-ink-gray-9">{{ title }}</h1>
			</div>
		</div>
		<div class="flex items-center gap-2"><slot /></div>
	</header>
</template>
