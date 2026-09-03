<script setup>
import { onMounted, onUnmounted, ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ToolPermissionsDialog from "../ToolPermissionsDialog.vue";
import MessageList from "@/components/MessageList.vue";
import Composer from "@/components/Composer.vue";
import { FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";

const {
	loadInitial,
	restoreSession,
	switchSession,
	newChat,
	scrollTick,
	selectedAgent,
	agentLabel,
	sessionName,
	recentSessions,
} = useStore();
const route = useRoute();
const router = useRouter();

const page = ref(null);
const composer = ref(null);
const toolsOpen = ref(false);
let observer = null;

const sessionTitle = computed(
	() => recentSessions.value.find((s) => s.name === sessionName.value)?.title || __("New chat"),
);

// The composer floats over the message list, so the list pads its bottom by the
// composer's live height (--flow-composer-h) — a grown composer (attachments,
// multiline text) must never cover the last message.
onMounted(async () => {
	await loadInitial();
	const requestedSession = route.params.session || null;
	if (requestedSession) await switchSession(requestedSession);
	else await restoreSession();

	observer = new ResizeObserver(([entry]) => {
		page.value?.style.setProperty("--flow-composer-h", `${entry.target.offsetHeight}px`);
		scrollTick.value++;
	});
	observer.observe(composer.value.$el);
});
onUnmounted(() => observer?.disconnect());

// Route -> store: opening a chat from the sidebar, a trigger log, or a macro
// run (or the browser's own back/forward) lands here with a route param —
// switch to it, but only when it actually differs from what's already
// loaded, so this doesn't re-trigger on the very change the store -> route
// watcher below just made.
watch(
	() => route.params.session || null,
	(session) => {
		if (session === sessionName.value) return;
		if (session) switchSession(session);
		else newChat();
	},
);

// Store -> route: keeps the URL in sync when the session changes some other
// way — most importantly, a brand-new chat's first turn only gets a real
// session name from the backend once the run starts (store.js's
// "run_started" handler), well after this component mounted on the bare "/"
// route with no session yet.
watch(sessionName, (name) => {
	const current = route.params.session || null;
	if (name === current) return;
	if (name) router.replace({ name: "chat-session", params: { session: name } });
	else router.replace({ name: "chat" });
});
</script>

<template>
	<div ref="page" class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white">
		<header
			class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-2.5"
		>
			<div class="min-w-0 truncate text-sm font-semibold text-ink-gray-9">
				{{ sessionTitle }}
			</div>
		</header>

		<MessageList />
		<Composer
			ref="composer"
			:disclaimer="
				__(
					'Flow can make mistakes. Verify important actions before submitting to ERPNext.',
				)
			"
		>
			<template #tools>
				<button
					class="flex h-6 items-center gap-1 rounded px-1.5 text-[12.5px] text-ink-gray-6 hover:bg-surface-gray-2"
					:disabled="!selectedAgent"
					:title="__('Tool permissions')"
					@click="toolsOpen = true"
				>
					<FeatherIcon name="sliders" class="h-3.5 w-3.5" />
				</button>
			</template>
		</Composer>

		<ToolPermissionsDialog
			v-model="toolsOpen"
			:agent="selectedAgent"
			:agent-label="agentLabel(selectedAgent)"
		/>
	</div>
</template>

<style scoped>
/* MessageList/Composer are shared with the floating widget (a much narrower
   fixed-width popup, where this is a no-op) — scoping the override here
   instead of editing those components keeps the widget's own width intact.
   `:deep()` needs an outer selector to actually attach this component's
   data-v- scope attribute — a bare `:deep(.max-w-3xl)` compiles unscoped and
   just ties with Tailwind's own !important rule on specificity, losing on
   source order. */
.relative :deep(.max-w-3xl) {
	max-width: 70rem !important;
}
</style>
