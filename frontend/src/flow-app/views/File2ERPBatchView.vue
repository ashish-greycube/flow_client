<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import FilePreviewPane from "@/components/FilePreviewPane.vue";
import EditableKeyValueTable from "@/components/EditableKeyValueTable.vue";
import EditableRowsTable from "@/components/EditableRowsTable.vue";
import { Badge, Breadcrumbs, Button, FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";
import {
	getFile2ERPBatch,
	removeFromBatch,
	startExtraction,
	createCombinedExpenseClaim,
} from "@/api/file2erp";

// One Expense Claim from several uploaded receipts: each file is still read on its own
// (in the background), and this page merges them — the claim's header once, every
// file's expense rows in one table — for one review and one Create. Create stays off
// until every file has been read, so no receipt is silently left out.
const props = defineProps({
	batch: { type: String, required: true },
});

const router = useRouter();

const loading = ref(true);
const creating = ref(false);
const busyEntry = ref("");
const data = ref(null);
const fields = ref({});
const rows = ref([]);
const selected = ref("");

const STATUS_THEME = {
	Uploaded: "gray",
	Processing: "blue",
	Extracted: "green",
	"Needs Review": "orange",
	Failed: "red",
	"Document Created": "green",
};
const PENDING_STATUSES = new Set(["Uploaded", "Processing"]);

const breadcrumbs = computed(() => [
	{ label: __("File2ERP"), route: { name: "file2erp" } },
	{
		label: __("Combined Expense Claim"),
		route: { name: "file2erp-batch", params: { batch: props.batch } },
	},
]);
const entries = computed(() => data.value?.entries || []);
const created = computed(() => !!data.value?.created_document);
const reading = computed(() => entries.value.some((e) => PENDING_STATUSES.has(e.status)));
const ready = computed(() => !created.value && !data.value?.not_ready?.length);
const selectedEntry = computed(() => entries.value.find((e) => e.name === selected.value) || entries.value[0]);
// Re-seed the editable tables only when a file's extraction actually changes — not on
// every poll, which would throw away edits in progress.
const resetKey = computed(() => props.batch + entries.value.map((e) => e.name + e.modified).join("|"));
const total = computed(() =>
	rows.value.reduce((sum, row) => sum + (parseFloat(row.amount) || 0), 0),
);

let pollTimer = null;

async function load() {
	const result = await getFile2ERPBatch(props.batch);
	const changed = !data.value || resetKey.value !== keyOf(result);
	data.value = result;
	if (changed) {
		fields.value = { ...result.fields };
		rows.value = result.line_items.map((row) => ({ ...row }));
	}
	if (!entries.value.some((e) => e.name === selected.value)) selected.value = entries.value[0]?.name || "";
	if (pollTimer) clearTimeout(pollTimer);
	if (reading.value) pollTimer = setTimeout(load, 3000);
}

function keyOf(result) {
	return props.batch + result.entries.map((e) => e.name + e.modified).join("|");
}

onMounted(async () => {
	try {
		await load();
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not load this claim."), indicator: "red" });
	} finally {
		loading.value = false;
	}
});
onUnmounted(() => {
	if (pollTimer) clearTimeout(pollTimer);
});

async function retry(entry) {
	busyEntry.value = entry.name;
	try {
		await startExtraction(entry.name, "Expense Claim", true);
		frappe.show_alert({ message: __("Reading {0} again…", [entry.file_name]), indicator: "blue" });
		await load();
		if (pollTimer) clearTimeout(pollTimer);
		pollTimer = setTimeout(load, 1500);
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not read the file again."), indicator: "red" });
	} finally {
		busyEntry.value = "";
	}
}

function confirmRemove(entry) {
	frappe.confirm(
		__('Remove "{0}" from this claim? It stays in File2ERP as its own file.', [entry.file_name]),
		async () => {
			busyEntry.value = entry.name;
			try {
				await removeFromBatch(entry.name);
				if (entries.value.length === 1) {
					router.push({ name: "file2erp" });
					return;
				}
				await load();
			} catch (e) {
				frappe.show_alert({ message: e?.message || __("Could not remove the file."), indicator: "red" });
			} finally {
				busyEntry.value = "";
			}
		},
	);
}

function openEntry(entry) {
	router.push({ name: "file2erp-detail", params: { name: entry.name } });
}

function confirmCreate() {
	frappe.confirm(
		__("Create one Expense Claim with {0} expense rows from {1} files?", [rows.value.length, entries.value.length]),
		createClaim,
	);
}

async function createClaim() {
	creating.value = true;
	try {
		const response = await createCombinedExpenseClaim(props.batch, fields.value, rows.value);
		const name = response?.result?.created?.[0];
		if (name) {
			frappe.show_alert({ message: __("Created {0}.", [name]), indicator: "green" });
			await load();
		} else {
			frappe.show_alert({
				message: response?.result?.failures?.[0]?.error || __("Could not create the Expense Claim."),
				indicator: "red",
			});
		}
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not create the Expense Claim."), indicator: "red" });
	} finally {
		creating.value = false;
	}
}

function openClaim() {
	window.open(frappe.utils.get_form_link(data.value.created_document_type, data.value.created_document), "_blank");
}

function formatAmount(value) {
	return window.format_currency ? format_currency(value, fields.value.currency) : value.toFixed(2);
}
</script>

<template>
	<div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-3">
			<Breadcrumbs :items="breadcrumbs" />
			<div v-if="data" class="flex items-center gap-2">
				<Badge variant="subtle" theme="gray" :label="__('{0} files', [entries.length])" />
				<Button v-if="created" variant="solid" theme="blue" @click="openClaim">
					<template #prefix><FeatherIcon name="external-link" class="h-3.5 w-3.5" /></template>
					{{ __("View {0}", [data.created_document]) }}
				</Button>
				<Button
					v-else
					variant="solid"
					:loading="creating"
					:disabled="!ready || !rows.length"
					@click="confirmCreate"
				>
					{{ __("Create Expense Claim") }}
				</Button>
			</div>
		</header>

		<div v-if="loading" class="flex flex-1 items-center justify-center">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>

		<div
			v-else-if="data"
			class="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] lg:grid-cols-[repeat(2,minmax(0,1fr))]"
		>
			<div class="flex min-h-0 min-w-0 flex-col border-b border-outline-gray-1 lg:border-b-0 lg:border-r">
				<div class="flex flex-wrap gap-1.5 px-6 pt-4 pb-2">
					<button
						v-for="entry in entries"
						:key="entry.name"
						class="max-w-[12rem] truncate rounded-md border px-2 py-1 text-xs"
						:class="
							entry.name === selectedEntry?.name
								? 'border-outline-gray-4 bg-surface-gray-2 text-ink-gray-9'
								: 'border-outline-gray-1 text-ink-gray-6 hover:bg-surface-gray-1'
						"
						@click="selected = entry.name"
					>
						{{ entry.file_name }}
					</button>
				</div>
				<div v-if="selectedEntry" class="min-h-0 min-w-0 flex-1">
					<FilePreviewPane
						:key="selectedEntry.name"
						:file-url="selectedEntry.file_url"
						:file-name="selectedEntry.file_name"
						:entry-name="selectedEntry.name"
					/>
				</div>
			</div>

			<div class="flow-scrollbar flex min-h-0 flex-col gap-6 overflow-y-auto px-6 py-5">
				<section>
					<h2 class="mb-2 text-sm font-medium text-ink-gray-7">{{ __("Files") }}</h2>
					<div class="overflow-hidden rounded-lg border border-outline-gray-1">
						<div
							v-for="entry in entries"
							:key="entry.name"
							class="flex items-center gap-3 border-b border-outline-gray-1 px-3 py-2 text-sm last:border-0"
						>
							<button
								class="min-w-0 flex-1 truncate text-left text-ink-gray-8 hover:underline"
								@click="selected = entry.name"
							>
								{{ entry.file_name }}
							</button>
							<span v-if="entry.status === 'Extracted' || entry.status === 'Document Created'" class="shrink-0 text-xs text-ink-gray-5">
								{{ __("{0} rows", [entry.expense_rows]) }}
							</span>
							<Spinner v-if="PENDING_STATUSES.has(entry.status)" class="h-3.5 w-3.5 shrink-0 text-ink-blue-3" />
							<Badge
								variant="subtle"
								:theme="STATUS_THEME[entry.status] || 'gray'"
								:label="__(entry.status)"
								class="shrink-0"
							/>
							<template v-if="!created">
								<Button
									v-if="entry.status === 'Failed' || entry.status === 'Needs Review'"
									size="sm"
									variant="outline"
									:loading="busyEntry === entry.name"
									@click="retry(entry)"
								>
									{{ __("Retry") }}
								</Button>
								<Button
									v-if="entry.status === 'Needs Review'"
									size="sm"
									variant="outline"
									@click="openEntry(entry)"
								>
									{{ __("Fix") }}
								</Button>
								<button
									class="flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-red-4"
									:title="__('Remove from claim')"
									:disabled="busyEntry === entry.name"
									@click="confirmRemove(entry)"
								>
									<FeatherIcon name="x" class="h-3.5 w-3.5" />
								</button>
							</template>
						</div>
					</div>
				</section>

				<div
					v-if="reading"
					class="flex items-start gap-3 rounded-lg border border-outline-blue-1 bg-surface-blue-1 px-4 py-3 text-sm"
					role="status"
					aria-live="polite"
				>
					<Spinner class="mt-0.5 h-4 w-4 shrink-0 text-ink-blue-3" />
					<span class="text-ink-blue-3">
						{{ __("Reading the receipts. Their expenses appear below as each one finishes.") }}
					</span>
				</div>
				<div
					v-else-if="!created && data.not_ready.length"
					class="rounded-lg border border-outline-amber-2 bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3"
				>
					<p class="font-medium">{{ __("Before creating the claim:") }}</p>
					<ul class="mt-1 list-disc pl-5">
						<li v-for="reason in data.not_ready" :key="reason">{{ reason }}</li>
					</ul>
				</div>

				<section>
					<h2 class="mb-2 text-sm font-medium text-ink-gray-7">{{ __("Claim Details") }}</h2>
					<EditableKeyValueTable v-model="fields" :reset-key="resetKey" :disabled="created" />
				</section>

				<section>
					<div class="mb-2 flex items-center justify-between">
						<h2 class="text-sm font-medium text-ink-gray-7">{{ __("Expenses") }}</h2>
						<span class="text-sm text-ink-gray-7">
							{{ __("Total: {0}", [formatAmount(total)]) }}
						</span>
					</div>
					<EditableRowsTable v-model="rows" :reset-key="resetKey" :disabled="created" />
				</section>
			</div>
		</div>
	</div>
</template>
