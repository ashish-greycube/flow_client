<script setup>
import { onMounted, onUnmounted, ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ToolPermissionsDialog from "../ToolPermissionsDialog.vue";
import SaveAsMacroDialog from "../SaveAsMacroDialog.vue";
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
	messages,
} = useStore();
const route = useRoute();
const router = useRouter();

const page = ref(null);
const composer = ref(null);
const toolsOpen = ref(false);
const actionMenuOpen = ref(false);
const macroDialogOpen = ref(false);
let observer = null;

const sessionTitle = computed(
	() => recentSessions.value.find((s) => s.name === sessionName.value)?.title || __("New chat"),
);

// Mirrors Jarvis's own "Save as macro": every user prompt in the conversation,
// in order, becomes a macro step.
const macroSteps = computed(() =>
	messages.value
		.filter((m) => m.role === "user" && m.content && m.content.trim())
		.map((m) => ({ label: "", prompt: m.content })),
);
const canSaveAsMacro = computed(() => macroSteps.value.length > 0);
const defaultMacroName = computed(() => {
	if (sessionName.value) return sessionTitle.value;
	const first = macroSteps.value[0]?.prompt || "";
	return first.length > 60 ? `${first.slice(0, 60)}…` : first;
});

function openSaveAsMacro() {
	actionMenuOpen.value = false;
	macroDialogOpen.value = true;
}

function openDesk() {
	window.open("/app", "_blank");
}

function openGuide() {
	frappe.set_route("flow-guide");
}

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
	<div ref="page" class="relative flex min-w-0 flex-1 flex-col bg-surface-white">
		<header
			class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-2.5"
		>
			<div class="min-w-0 truncate text-sm font-semibold text-ink-gray-9">
				{{ sessionTitle }}
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					class="flex items-center gap-1.5 rounded-md border border-outline-gray-2 px-2.5 py-1 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
					@click="openGuide"
				>
					<FeatherIcon name="help-circle" class="h-3.5 w-3.5" />
					{{ __("Flow Guide") }}
				</button>
				<div v-if="canSaveAsMacro" class="relative">
					<button
						class="flex items-center gap-1.5 rounded-md border border-outline-gray-2 px-2.5 py-1 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
						@click="actionMenuOpen = !actionMenuOpen"
					>
						{{ __("Action") }}
						<FeatherIcon name="chevron-down" class="h-3 w-3" />
					</button>
					<template v-if="actionMenuOpen">
						<div class="fixed inset-0 z-40" @click="actionMenuOpen = false"></div>
						<div
							class="absolute right-0 top-[calc(100%+6px)] z-50 w-64 rounded-xl border border-outline-gray-2 bg-surface-white p-1.5 shadow-2xl"
						>
							<button
								class="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-surface-gray-2"
								@click="openSaveAsMacro"
							>
								<FeatherIcon
									name="layers"
									class="mt-0.5 h-4 w-4 shrink-0 text-ink-gray-6"
								/>
								<span>
									<span class="block text-sm font-medium text-ink-gray-9">{{
										__("Save as macro")
									}}</span>
									<span class="block text-xs text-ink-gray-5">{{
										__("Reuse these prompts on demand")
									}}</span>
								</span>
							</button>
						</div>
					</template>
				</div>
				<button
					type="button"
					class="flex h-7 w-7 items-center justify-center rounded-md border border-outline-gray-2 text-ink-gray-7 hover:bg-surface-gray-2"
					:title="__('Open ERPNext Desk')"
					:aria-label="__('Open ERPNext Desk')"
					@click="openDesk"
				>
					<FeatherIcon name="external-link" class="h-3.5 w-3.5" />
				</button>
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
		<SaveAsMacroDialog
			v-model="macroDialogOpen"
			:agent="selectedAgent"
			:agent-label="agentLabel(selectedAgent)"
			:steps="macroSteps"
			:default-name="defaultMacroName"
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
