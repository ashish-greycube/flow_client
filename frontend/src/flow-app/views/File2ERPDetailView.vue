<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import FilePreviewPane from "@/components/FilePreviewPane.vue";
import EditableKeyValueTable from "@/components/EditableKeyValueTable.vue";
import EditableRowsTable from "@/components/EditableRowsTable.vue";
import { Badge, Breadcrumbs, Button, FeatherIcon, Spinner, TextInput, Textarea } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { useStore } from "@/store";
import {
	getFile2ERPEntry,
	updateFile2ERPData,
	openChatSession,
	createDocumentFromEntry,
	deleteFile2ERPEntry,
	startExtraction,
} from "@/api/file2erp";

const props = defineProps({
	name: { type: String, required: true },
});

const router = useRouter();
const { attachments, newChat, send } = useStore();

const loading = ref(true);
const saving = ref(false);
const opening = ref(false);
const creating = ref(false);
const asking = ref(false);
const deleting = ref(false);
const extracting = ref(false);
const entry = ref(null);
const fields = ref({});
const lineItems = ref([]);
const targetDoctype = ref("");
const documentType = ref("Expense Claim");
const promptText = ref("");
// Bridges the gap between clicking "Extract Data" and the background job actually
// flipping status to "Processing" — start_extraction's response is still "Uploaded"
// the instant it returns (the job was only just enqueued), so load()'s own status
// check alone would stop polling right where it matters most.
const awaitingExtraction = ref(false);

// Mirrors Flow File2ERP's own document_type Select options (flow_file2erp.json) —
// hardcoded here too since that's the authoritative, already-installed-filtered list
// the backend itself offers; no need for a second round trip just to fetch it.
const DOCUMENT_TYPE_OPTIONS = [
	"Expense Claim",
	"Sales Invoice",
	"Purchase Invoice",
	"Purchase Order",
	"Sales Order",
	"Payment Entry",
];

const STATUS_THEME = {
	Uploaded: "gray",
	Processing: "blue",
	Extracted: "green",
	"Needs Review": "orange",
	Failed: "red",
	"Document Created": "green",
};
const PENDING_STATUSES = new Set(["Processing"]);

const breadcrumbs = computed(() => [
	{ label: __("File2ERP"), route: { name: "file2erp" } },
	{ label: entry.value?.file_name || props.name, route: { name: "file2erp-detail", params: { name: props.name } } },
]);
const editable = computed(() => !!entry.value && entry.value.status !== "Document Created");

// Compared against JS-side JSON.stringify snapshots taken right after load/save, not
// the raw backend string — Python's json.dumps and JS's JSON.stringify don't agree on
// key order, so comparing against the backend string directly would mark the form
// dirty immediately after every load even with no edits.
const savedFieldsSnapshot = ref("{}");
const savedLineItemsSnapshot = ref("[]");
const dirty = computed(() => {
	if (!entry.value) return false;
	return (
		JSON.stringify(fields.value) !== savedFieldsSnapshot.value ||
		JSON.stringify(lineItems.value) !== savedLineItemsSnapshot.value
	);
});

let pollTimer = null;

async function load() {
	entry.value = await getFile2ERPEntry(props.name);
	fields.value = entry.value.extracted_fields ? JSON.parse(entry.value.extracted_fields) : {};
	lineItems.value = entry.value.extracted_line_items ? JSON.parse(entry.value.extracted_line_items) : [];
	savedFieldsSnapshot.value = JSON.stringify(fields.value);
	savedLineItemsSnapshot.value = JSON.stringify(lineItems.value);
	documentType.value = entry.value.document_type || documentType.value;
	targetDoctype.value = entry.value.document_type || targetDoctype.value;
	if (entry.value.status !== "Uploaded") awaitingExtraction.value = false;
	if (PENDING_STATUSES.has(entry.value.status) || awaitingExtraction.value) {
		pollTimer = setTimeout(load, 3000);
	}
}

// Merges an API response into entry.value instead of replacing it outright: several
// backend endpoints (start_extraction, update_file2erp_data) return doc.as_dict(),
// which has no file_url key at all (that join only happens in get_file2erp_entry) — a
// wholesale replace would null out FilePreviewPane's :file-url prop and make the
// preview flash away for a few seconds until the next poll's load() restores it.
function mergeEntry(response) {
	entry.value = { ...entry.value, ...response };
}

async function startExtractionClick(force = false) {
	extracting.value = true;
	awaitingExtraction.value = true;
	try {
		mergeEntry(await startExtraction(props.name, documentType.value, force));
		if (pollTimer) clearTimeout(pollTimer);
		pollTimer = setTimeout(load, 1500);
	} catch (e) {
		awaitingExtraction.value = false;
		frappe.show_alert({
			message: e?.message || __(force ? "Could not re-extract data." : "Could not start extraction."),
			indicator: "red",
		});
	} finally {
		extracting.value = false;
	}
}

onMounted(async () => {
	try {
		await load();
	} finally {
		loading.value = false;
	}
});
onUnmounted(() => {
	if (pollTimer) clearTimeout(pollTimer);
});

async function save() {
	saving.value = true;
	try {
		mergeEntry(await updateFile2ERPData(props.name, fields.value, lineItems.value));
		savedFieldsSnapshot.value = JSON.stringify(fields.value);
		savedLineItemsSnapshot.value = JSON.stringify(lineItems.value);
		frappe.show_alert({ message: __("Saved."), indicator: "green" });
	} finally {
		saving.value = false;
	}
}

// Shared by "Open Chat" and "Ask AI": stage this entry's already-extracted (and
// possibly user-edited) text as a chat attachment and switch the store over to a
// fresh chat — no re-parsing, since open_chat_session reuses what's already stored.
async function stageChat() {
	if (dirty.value) await save();
	const chip = await openChatSession(props.name);
	newChat();
	attachments.value.push({
		uid: `file2erp-${props.name}`,
		file: chip.file,
		file_name: chip.file_name,
		file_size: chip.file_size,
		status: "ready",
		error: "",
	});
}

async function openChat() {
	opening.value = true;
	try {
		await stageChat();
		router.push({ name: "chat" });
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not open chat."), indicator: "red" });
	} finally {
		opening.value = false;
	}
}

// Lets the user act on this file without leaving the page: stage it the same way
// "Open Chat" does, then immediately send the typed instruction as the first
// message — the OCR Agent gets the file's reviewed data via get_file2erp_data and
// can correct fields, map to a DocType, or create a document from a plain request.
async function askAI() {
	const text = promptText.value.trim();
	if (!text) return;
	asking.value = true;
	try {
		await stageChat();
		promptText.value = "";
		router.push({ name: "chat" });
		send(text);
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not send to AI."), indicator: "red" });
	} finally {
		asking.value = false;
	}
}

function confirmCreate() {
	if (!targetDoctype.value.trim()) {
		frappe.show_alert({ message: __("Choose a document type first."), indicator: "red" });
		return;
	}
	frappe.confirm(
		__("Create a new {0} from this file's reviewed data?", [targetDoctype.value.trim()]),
		createDocument,
	);
}

async function createDocument() {
	creating.value = true;
	try {
		if (dirty.value) await save();
		const result = await createDocumentFromEntry(props.name, targetDoctype.value.trim());
		const created = result?.result?.created?.[0];
		const failed = result?.result?.failures?.length;
		if (created) {
			const missing = result?.missing_mandatory || [];
			frappe.show_alert({
				message: missing.length
					? __("Created {0} — review these required fields: {1}", [created, missing.join(", ")])
					: __("Created {0}.", [created]),
				indicator: missing.length ? "orange" : "green",
			});
			entry.value = await getFile2ERPEntry(props.name);
		} else if (failed) {
			frappe.show_alert({
				message: result.result.failures[0]?.error || __("Could not create the document."),
				indicator: "red",
			});
		}
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not create the document."), indicator: "red" });
	} finally {
		creating.value = false;
	}
}

function openCreatedDocument() {
	if (entry.value?.created_document_type && entry.value?.created_document) {
		const route = frappe.utils.get_form_link(entry.value.created_document_type, entry.value.created_document);
		window.open(route, "_blank");
	}
}

function confirmDelete() {
	frappe.confirm(
		__('Delete "{0}"? This cannot be undone.', [entry.value?.file_name || props.name]),
		deleteEntry,
	);
}

async function deleteEntry() {
	deleting.value = true;
	try {
		await deleteFile2ERPEntry(props.name);
		router.push({ name: "file2erp" });
	} catch (e) {
		frappe.show_alert({ message: e?.message || __("Could not delete this entry."), indicator: "red" });
	} finally {
		deleting.value = false;
	}
}
</script>

<template>
	<div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-3">
			<Breadcrumbs :items="breadcrumbs" />
			<div v-if="entry" class="flex items-center gap-2">
				<Badge variant="subtle" :theme="STATUS_THEME[entry.status] || 'gray'" :label="__(entry.status)" />
				<Button
					v-if="entry.created_document_type"
					variant="solid"
					theme="blue"
					@click="openCreatedDocument"
				>
					<template #prefix><FeatherIcon name="external-link" class="h-3.5 w-3.5" /></template>
					{{ __("View {0}", [entry.created_document]) }}
				</Button>
				<Button
					variant="outline"
					:loading="opening"
					:disabled="entry.status === 'Uploaded'"
					@click="openChat"
				>
					<template #prefix><FeatherIcon name="message-circle" class="h-3.5 w-3.5" /></template>
					{{ __("Open Chat") }}
				</Button>
				<Button variant="subtle" :loading="saving" :disabled="!editable || !dirty" @click="save">
					{{ __("Save") }}
				</Button>
				<button
					class="flex h-7 w-7 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-red-4"
					:title="__('Delete')"
					:disabled="deleting"
					@click="confirmDelete"
				>
					<FeatherIcon name="trash-2" class="h-3.5 w-3.5" />
				</button>
			</div>
		</header>

		<div v-if="loading" class="flex flex-1 items-center justify-center">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>

		<div v-else-if="entry" class="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-2">
			<div class="flex min-h-0 flex-col border-b border-outline-gray-1 lg:border-b-0 lg:border-r">
				<h2 class="px-6 pt-5 pb-2 text-sm font-medium text-ink-gray-7">{{ __("Preview") }}</h2>
				<div class="min-h-0 flex-1">
					<FilePreviewPane :file-url="entry.file_url" :file-name="entry.file_name" />
				</div>
			</div>

			<div class="flow-scrollbar flex min-h-0 flex-col gap-6 overflow-y-auto px-6 py-5">
				<!-- Pre-extraction: nothing extracted yet, and won't be until the user
				     confirms what this file should become — extraction is scoped to just
				     that DocType's own fields, so there's nothing useful to show below
				     until this choice is made. -->
				<div
					v-if="entry.status === 'Uploaded'"
					class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 p-4"
				>
					<div>
						<label class="text-sm font-medium text-ink-gray-7">{{ __("Document Type") }}</label>
						<p class="mt-1 text-xs text-ink-gray-5">
							{{
								__(
									"Choose what this file should become. Extraction is scoped to just this DocType's own fields — nothing else is extracted.",
								)
							}}
						</p>
					</div>
					<select
						v-model="documentType"
						class="h-8 w-64 rounded border border-outline-gray-2 bg-surface-white px-2 text-sm text-ink-gray-8 outline-none focus:border-outline-gray-4"
					>
						<option v-for="opt in DOCUMENT_TYPE_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
					</select>
					<Button variant="solid" :loading="extracting" class="self-start" @click="startExtractionClick()">
						{{ __("Extract Data") }}
					</Button>
				</div>

				<template v-else>
					<div v-if="PENDING_STATUSES.has(entry.status) || awaitingExtraction" class="flex items-center gap-2 text-sm text-ink-gray-5">
						<Spinner class="h-4 w-4" />
						{{ __("Extracting…") }}
					</div>
					<div v-if="entry.error" class="rounded-lg border border-outline-red-2 bg-surface-red-1 px-3 py-2 text-sm text-ink-red-4">
						{{ entry.error }}
					</div>

					<div v-if="editable" class="flex justify-end">
						<Button variant="outline" size="sm" :loading="extracting" @click="startExtractionClick(true)">
							<template #prefix><FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" /></template>
							{{ __("Re-extract Data") }}
						</Button>
					</div>

					<section class="flex items-end gap-2 border-b border-outline-gray-1 pb-4">
						<TextInput
							v-model="targetDoctype"
							:label="__('Create Document')"
							:placeholder="__('e.g. Sales Invoice')"
							:disabled="!editable"
							class="flex-1"
						/>
						<Button variant="solid" :loading="creating" :disabled="!editable" @click="confirmCreate">
							{{ __("Create") }}
						</Button>
					</section>

					<section>
						<h2 class="mb-2 text-sm font-medium text-ink-gray-7">{{ __("Fields") }}</h2>
						<EditableKeyValueTable
							v-model="fields"
							:reset-key="entry.name + entry.modified"
							:disabled="!editable"
						/>
					</section>

					<section>
						<h2 class="mb-2 text-sm font-medium text-ink-gray-7">{{ __("Line Items") }}</h2>
						<EditableRowsTable
							v-model="lineItems"
							:reset-key="entry.name + entry.modified"
							:disabled="!editable"
						/>
					</section>

					<section class="mt-auto flex flex-col gap-2 border-t border-outline-gray-1 pt-4">
						<h2 class="text-sm font-medium text-ink-gray-7">{{ __("Ask AI") }}</h2>
						<div class="flex items-end gap-2">
							<Textarea
								v-model="promptText"
								:placeholder="__('e.g. Fix the total amount, map this to a Purchase Invoice, or just ask a question…')"
								:disabled="!editable"
								:rows="2"
								class="flex-1"
							/>
							<Button
								variant="solid"
								:loading="asking"
								:disabled="!editable || !promptText.trim()"
								@click="askAI"
							>
								{{ __("Send") }}
							</Button>
						</div>
					</section>
				</template>
			</div>
		</div>
	</div>
</template>
