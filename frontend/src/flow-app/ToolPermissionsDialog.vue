<script setup>
import { ref, computed, watch } from "vue";
import PanelDropdown from "@/components/PanelDropdown.vue";
import { Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { getAgentToolPermissions, setAgentToolPermissions } from "@/api/client";

// A plain fixed-overlay modal — never teleported — so it stays inside #flow-root
// and picks up the page's scoped styles, the same reason PanelDropdown.vue exists
// instead of frappe-ui's own (teleporting) Dialog/Dropdown.
const props = defineProps({
	modelValue: { type: Boolean, default: false },
	agent: { type: String, default: null },
	agentLabel: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const PERMISSIONS = [
	{ value: "Always Allow", label: __("Always allow"), icon: "check-circle" },
	{ value: "Needs Approval", label: __("Needs approval"), icon: "pause-circle" },
	{ value: "Blocked", label: __("Blocked"), icon: "slash" },
];
const PERMISSION_ITEMS = PERMISSIONS.map((p) => ({ value: p.value, label: p.label }));

const loading = ref(false);
const rows = ref([]); // [{ tool, title, requires_confirmation, permission }]

// The tool's own default (Flow Tool.requires_confirmation) draws the line between
// the two groups — matches how the resolver treats a row with no override.
const readOnly = computed(() => rows.value.filter((r) => !r.requires_confirmation));
const writeDelete = computed(() => rows.value.filter((r) => r.requires_confirmation));

function effective(row) {
	return row.permission || (row.requires_confirmation ? "Needs Approval" : "Always Allow");
}

async function load() {
	if (!props.agent) return;
	loading.value = true;
	try {
		rows.value = await getAgentToolPermissions(props.agent);
	} finally {
		loading.value = false;
	}
}

watch(
	() => [props.modelValue, props.agent],
	([open]) => {
		if (open) load();
	}
);

function close() {
	emit("update:modelValue", false);
}

// Optimistic: the row updates immediately, the request runs behind it. A failure
// rolls the row back so the dialog never drifts from what's actually saved.
async function setOne(row, value) {
	if (effective(row) === value) return;
	const previous = row.permission;
	row.permission = value;
	try {
		await setAgentToolPermissions(props.agent, { [row.tool]: value });
	} catch (e) {
		row.permission = previous;
		frappe.show_alert({ message: e.message || __("Could not save permission."), indicator: "red" });
	}
}

async function setGroup(targets, value) {
	if (!targets.length) return;
	const previous = targets.map((r) => r.permission);
	targets.forEach((r) => (r.permission = value));
	try {
		await setAgentToolPermissions(
			props.agent,
			Object.fromEntries(targets.map((r) => [r.tool, value]))
		);
	} catch (e) {
		targets.forEach((r, i) => (r.permission = previous[i]));
		frappe.show_alert({ message: e.message || __("Could not save permissions."), indicator: "red" });
	}
}

// The bulk dropdown's own label: the shared state when every tool in the group
// agrees, otherwise "Mixed" so the control never claims a value that isn't true
// for every row.
function groupValue(list) {
	if (!list.length) return null;
	const first = effective(list[0]);
	return list.every((r) => effective(r) === first) ? first : null;
}
function groupLabel(list) {
	const value = groupValue(list);
	return value ? PERMISSIONS.find((p) => p.value === value).label : __("Mixed");
}
</script>

<template>
	<template v-if="modelValue">
		<div class="fixed inset-0 z-40 bg-black/40" @click="close"></div>
		<div
			class="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[36rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-2xl"
		>
			<header class="flex items-center justify-between border-b border-outline-gray-1 px-4 py-3">
				<div>
					<div class="text-sm font-semibold text-ink-gray-9">{{ __("Tool Permissions") }}</div>
					<div v-if="agentLabel" class="text-xs text-ink-gray-5">
						{{ __("Tools available to {0}", [agentLabel]) }}
					</div>
				</div>
				<button
					class="flex h-6 w-6 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
					:title="__('Close')"
					@click="close"
				>
					<FeatherIcon name="x" class="h-3.5 w-3.5" />
				</button>
			</header>

			<div v-if="loading" class="flex justify-center py-10">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>
			<div v-else-if="!rows.length" class="py-10 text-center text-sm text-ink-gray-5">
				{{ __("This agent has no tools configured.") }}
			</div>

			<div v-else class="flow-scrollbar flex flex-col gap-5 overflow-y-auto px-4 py-4">
				<section v-if="readOnly.length">
					<div class="mb-1.5 flex items-center justify-between">
						<div class="flex items-center gap-2">
							<span class="text-sm font-medium text-ink-gray-8">{{
								__("Read-only tools")
							}}</span>
							<span class="rounded-full bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{
								readOnly.length
							}}</span>
						</div>
						<PanelDropdown
							:items="PERMISSION_ITEMS"
							:model-value="groupValue(readOnly)"
							align="right"
							placement="bottom"
							@update:model-value="(v) => setGroup(readOnly, v)"
						>
							<template #trigger="{ toggle }">
								<button
									class="flex items-center gap-1 rounded-md border border-outline-gray-2 px-2.5 py-1 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
									@click="toggle"
								>
									{{ groupLabel(readOnly) }}
									<FeatherIcon name="chevron-down" class="h-3 w-3" />
								</button>
							</template>
						</PanelDropdown>
					</div>
					<div class="flex flex-col rounded-lg border border-outline-gray-1">
						<div
							v-for="row in readOnly"
							:key="row.tool"
							class="flex items-center justify-between border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
						>
							<span class="text-sm text-ink-gray-8">{{ row.title }}</span>
							<div class="flex items-center gap-1">
								<button
									v-for="p in PERMISSIONS"
									:key="p.value"
									:title="p.label"
									class="flex h-6 w-6 items-center justify-center rounded-full border"
									:class="
										effective(row) === p.value
											? 'border-outline-gray-2 bg-surface-gray-2 text-ink-gray-8'
											: 'border-transparent text-ink-gray-4 hover:bg-surface-gray-2'
									"
									@click="setOne(row, p.value)"
								>
									<FeatherIcon :name="p.icon" class="h-3.5 w-3.5" />
								</button>
							</div>
						</div>
					</div>
				</section>

				<section v-if="writeDelete.length">
					<div class="mb-1.5 flex items-center justify-between">
						<div class="flex items-center gap-2">
							<span class="text-sm font-medium text-ink-gray-8">{{
								__("Write/delete tools")
							}}</span>
							<span class="rounded-full bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{
								writeDelete.length
							}}</span>
						</div>
						<PanelDropdown
							:items="PERMISSION_ITEMS"
							:model-value="groupValue(writeDelete)"
							align="right"
							placement="bottom"
							@update:model-value="(v) => setGroup(writeDelete, v)"
						>
							<template #trigger="{ toggle }">
								<button
									class="flex items-center gap-1 rounded-md border border-outline-gray-2 px-2.5 py-1 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
									@click="toggle"
								>
									{{ groupLabel(writeDelete) }}
									<FeatherIcon name="chevron-down" class="h-3 w-3" />
								</button>
							</template>
						</PanelDropdown>
					</div>
					<div class="flex flex-col rounded-lg border border-outline-gray-1">
						<div
							v-for="row in writeDelete"
							:key="row.tool"
							class="flex items-center justify-between border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
						>
							<span class="text-sm text-ink-gray-8">{{ row.title }}</span>
							<div class="flex items-center gap-1">
								<button
									v-for="p in PERMISSIONS"
									:key="p.value"
									:title="p.label"
									class="flex h-6 w-6 items-center justify-center rounded-full border"
									:class="
										effective(row) === p.value
											? 'border-outline-gray-2 bg-surface-gray-2 text-ink-gray-8'
											: 'border-transparent text-ink-gray-4 hover:bg-surface-gray-2'
									"
									@click="setOne(row, p.value)"
								>
									<FeatherIcon :name="p.icon" class="h-3.5 w-3.5" />
								</button>
							</div>
						</div>
					</div>
				</section>
			</div>

			<footer class="flex justify-end border-t border-outline-gray-1 px-4 py-3">
				<Button variant="solid" @click="close">{{ __("Done") }}</Button>
			</footer>
		</div>
	</template>
</template>
