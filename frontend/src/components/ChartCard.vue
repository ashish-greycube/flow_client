<script setup>
import { computed } from "vue";
import useAxisChartOptions from "frappe-ui/src/components/Charts/axisChartOptions";
import useDonutChartOptions from "frappe-ui/src/components/Charts/donutChartOptions";
import useFunnelChartOptions from "frappe-ui/src/components/Charts/funnelChartOptions";
import LazyECharts from "./LazyECharts.vue";
import { NumberChart } from "@/lib/ui";

// Renders a create_chart tool result (see AssistantMessage.vue's item
// grouping and lib/toolMeta.js's chartPayload()). "number" needs no charting
// library at all (frappe-ui's NumberChart is plain HTML/CSS); axis/donut/
// funnel each go through their own frappe-ui option-builder to the same
// LazyECharts renderer — see lib/ui.js's note on why these aren't frappe-ui's
// own AxisChart/DonutChart/FunnelChart.vue wrapper components.
const props = defineProps({ chart: { type: Object, required: true } });

const OPTION_BUILDERS = { axis: useAxisChartOptions, donut: useDonutChartOptions, funnel: useFunnelChartOptions };

const echartsOptions = computed(() => {
	const build = OPTION_BUILDERS[props.chart.kind];
	if (!build) return null;
	try {
		return build(props.chart.config);
	} catch {
		return null;
	}
});

// frappe-ui's option builders color axis/title text via the app's own
// --ink-gray-* custom properties (theme.css), which flip to light-on-dark
// values under #flow-root[data-theme="dark"]. echarts itself only ever
// draws the "light" theme (LazyECharts.vue), so those flipped values land
// as near-white text on this card's own white background and disappear.
// Pinning the light-mode values here via inline style (highest specificity,
// so it wins regardless of theme.css's cascade order) keeps the chart
// readable in both app themes without touching theme.css's own dark tokens.
const LIGHT_TOKENS = {
	"--surface-white": "#ffffff",
	"--ink-gray-9": "#0f172a",
	"--ink-gray-8": "#12263a",
	"--ink-gray-7": "#12263a",
	"--ink-gray-6": "#5b6472",
	"--ink-gray-5": "#5b6472",
	"--ink-gray-4": "#5b6472",
	"--ink-gray-3": "#5b6472",
};
</script>

<template>
	<div
		v-if="chart.kind === 'number'"
		class="my-1.5 max-w-3xl overflow-hidden rounded-xl border border-outline-gray-1 bg-white"
		:style="LIGHT_TOKENS"
	>
		<NumberChart :config="chart.config" />
	</div>
	<div
		v-else-if="echartsOptions"
		class="my-1.5 max-w-3xl overflow-hidden rounded-xl border border-outline-gray-1 bg-white"
		:style="LIGHT_TOKENS"
	>
		<LazyECharts :options="echartsOptions" />
	</div>
</template>
