<script setup>
import { ref, computed, watch, onUnmounted } from "vue";
import { __ } from "@/lib/translate";

// Live-ticking while the message is pending, frozen once it's done. Reads
// message.startedAt/elapsedMs, which store.js maintains across a turn (including
// pause/resume for approvals).
const props = defineProps({ message: { type: Object, required: true } });

const now = ref(Date.now());
let timer = null;

function start() {
	if (timer) return;
	now.value = Date.now();
	timer = setInterval(() => (now.value = Date.now()), 1000);
}
function stop() {
	clearInterval(timer);
	timer = null;
}

watch(
	() => props.message.pending,
	(pending) => (pending ? start() : stop()),
	{ immediate: true },
);
onUnmounted(stop);

const ms = computed(() => {
	const base = props.message.elapsedMs || 0;
	if (!props.message.pending || props.message.startedAt == null) return base;
	return base + (now.value - props.message.startedAt);
});

const label = computed(() => {
	const s = Math.max(0, Math.round(ms.value / 1000));
	if (s < 60) return __("{0}s", [s]);
	return __("{0}m {1}s", [Math.floor(s / 60), String(s % 60).padStart(2, "0")]);
});
</script>

<template>
	<span class="text-xs text-ink-gray-4">{{ label }}</span>
</template>
