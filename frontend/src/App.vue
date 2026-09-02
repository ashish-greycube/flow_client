<script setup>
import { onMounted, onUnmounted, ref, nextTick, watch } from "vue";
import PanelHeader from "./components/PanelHeader.vue";
import MessageList from "./components/MessageList.vue";
import Composer from "./components/Composer.vue";
import { FeatherIcon } from "./lib/ui";
import { useStore } from "./store";
import { __ } from "./lib/translate";

// Floating chat widget: an always-visible launcher button plus a small popup
// (this component), injected into every desk page. Mounted imperatively by
// main.js (a plain class, not a Vue app), which drives `visible` through the
// methods exposed below — see main.js's FlowWidget for why.
const props = defineProps({
	onOpenFullChat: { type: Function, default: null },
});
const { loadInitial, restoreSession, scrollTick } = useStore();

const visible = ref(false);
const panel = ref(null);
const composer = ref(null);
let observer = null;

onMounted(() => loadInitial());

// The popup is `v-if`, not `v-show`: this app's tailwind.config sets
// `important: true` (so its utilities can out-rank the desk's own Bootstrap
// classes), which means a `flex`/`block` utility's `!important` beats v-show's
// plain inline `display:none` — the same reason every other conditional panel
// in this app (SessionsMenu, the dialogs) uses `v-if`. That destroys and
// remounts the composer each time it opens, so the ResizeObserver — which
// sizes the message list's bottom padding to the composer's live height via
// --flow-composer-h — is (re)wired here instead of once in onMounted.
watch(visible, async (v) => {
	observer?.disconnect();
	observer = null;
	if (!v) return;
	await nextTick();
	observer = new ResizeObserver(([entry]) => {
		panel.value?.style.setProperty("--flow-composer-h", `${entry.target.offsetHeight}px`);
		scrollTick.value++;
	});
	observer.observe(composer.value.$el);
});
onUnmounted(() => observer?.disconnect());

function show() {
	visible.value = true;
	restoreSession();
}
function hide() {
	visible.value = false;
}
function toggle() {
	visible.value ? hide() : show();
}
defineExpose({ show, hide, toggle });
</script>

<template>
	<div class="flow-widget-anchor">
		<div
			v-if="visible"
			ref="panel"
			class="flow-panel flow-widget-popup relative flex flex-col overflow-hidden rounded-2xl border border-outline-gray-2 bg-surface-white text-ink-gray-9 shadow-2xl"
		>
			<PanelHeader :on-open-full-chat="props.onOpenFullChat" @close="hide" />
			<MessageList />
			<Composer ref="composer" />
		</div>

		<button
			class="flow-widget-launcher flex items-center justify-center rounded-full bg-surface-gray-7 text-ink-white shadow-2xl"
			:title="visible ? __('Close chat') : __('Chat with Flow')"
			@click="toggle"
		>
			<FeatherIcon :name="visible ? 'x' : 'message-circle'" class="h-6 w-6" />
		</button>
	</div>
</template>
