<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import SaveAsMacroDialog from "./SaveAsMacroDialog.vue";
import { FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";
import { currentTheme, toggleTheme } from "@/lib/theme";

// Persistent across every route (rendered once in Shell.vue, a sibling of
// <RouterView>, not inside any per-view header) — Flow Guide / Open Desk /
// theme are global utilities, not chat-specific, and "sticky to all pages"
// falls out of that placement for free: this never sits inside a view's own
// scrolling container, so there's no scroll-under to guard against with
// position:sticky.
const route = useRoute();
const { selectedAgent, agentLabel, sessionName, recentSessions, messages } = useStore();

const isDark = ref(currentTheme() === "dark");
const actionMenuOpen = ref(false);
const macroDialogOpen = ref(false);

const onChatRoute = computed(() => route.name === "chat" || route.name === "chat-session");

const sessionTitle = computed(
	() => recentSessions.value.find((s) => s.name === sessionName.value)?.title || __("New chat")
);

// "Save as macro" logic, moved here verbatim from ChatView.vue — only the
// Action control's *home* changed (global navbar instead of the chat view's
// own header), not when it's available: still gated on an actual session
// with real user turns in it, same as before.
const macroSteps = computed(() =>
	messages.value
		.filter((m) => m.role === "user" && m.content && m.content.trim())
		.map((m) => ({ label: "", prompt: m.content }))
);
const canSaveAsMacro = computed(() => onChatRoute.value && macroSteps.value.length > 0);
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

function onToggleTheme() {
	toggleTheme();
	isDark.value = currentTheme() === "dark";
}
</script>

<template>
	<header
		class="flex h-12 shrink-0 items-center justify-end gap-2 border-b border-outline-gray-1 bg-surface-white px-4"
	>
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
						<FeatherIcon name="layers" class="mt-0.5 h-4 w-4 shrink-0 text-ink-gray-6" />
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
			:title="isDark ? __('Switch to light mode') : __('Switch to dark mode')"
			:aria-label="isDark ? __('Switch to light mode') : __('Switch to dark mode')"
			@click="onToggleTheme"
		>
			<FeatherIcon :name="isDark ? 'sun' : 'moon'" class="h-3.5 w-3.5" />
		</button>

		<button
			type="button"
			class="flex h-7 w-7 items-center justify-center rounded-md border border-outline-gray-2 text-ink-gray-7 hover:bg-surface-gray-2"
			:title="__('Open ERPNext Desk')"
			:aria-label="__('Open ERPNext Desk')"
			@click="openDesk"
		>
			<FeatherIcon name="external-link" class="h-3.5 w-3.5" />
		</button>

		
	</header>

	<SaveAsMacroDialog
		v-model="macroDialogOpen"
		:agent="selectedAgent"
		:agent-label="agentLabel(selectedAgent)"
		:steps="macroSteps"
		:default-name="defaultMacroName"
	/>
</template>
