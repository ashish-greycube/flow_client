<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { loadEcharts } from "@/lib/loadEcharts";

// A drop-in for frappe-ui's own ECharts.vue, minus the static `import
// "echarts"` — see loadEcharts.js for why. Same init call (light theme, svg
// renderer) so charts built from frappe-ui's own option builders
// (axisChartOptions/donutChartOptions/funnelChartOptions) render identically.
const props = defineProps({ options: { type: Object, required: true } });

const chartDiv = ref(null);
const error = ref("");
let chart = null;
let resizeObserver = null;

onMounted(async () => {
	try {
		const echarts = await loadEcharts();
		if (!chartDiv.value) return; // unmounted while the script was loading
		chart = echarts.init(chartDiv.value, "light", { renderer: "svg" });
		chart.setOption(props.options, true);
		resizeObserver = new ResizeObserver(() => chart?.resize());
		resizeObserver.observe(chartDiv.value);
	} catch (e) {
		error.value = e.message || "Could not load the charting library.";
	}
});

watch(
	() => props.options,
	(next) => chart?.setOption(next, true),
	{ deep: true }
);

onBeforeUnmount(() => {
	resizeObserver?.disconnect();
	chart?.dispose();
});
</script>

<template>
	<div ref="chartDiv" v-show="!error" dir="ltr" class="h-[300px] min-h-[300px] w-full min-w-[280px] px-4 py-2"></div>
	<div
		v-show="error"
		class="flex h-[120px] w-full items-center justify-center text-center text-sm text-ink-red-3"
	>
		{{ error }}
	</div>
</template>
