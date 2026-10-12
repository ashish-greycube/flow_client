<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import SearchInput from "@/components/SearchInput.vue";
import { Button, FeatherIcon, Spinner, Badge } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { uploadFile } from "@/api/client";
import { createFile2ERPEntry, listFile2ERPEntries, deleteFile2ERPEntry } from "@/api/file2erp";

const router = useRouter();

const loading = ref(true);
const entries = ref([]);
const query = ref("");
const dragging = ref(false);
const uploading = ref(false);
// What the upload banner shows while a batch is in flight: which file (of how many)
// and which step — sending the bytes, then registering the File2ERP entry.
const uploadProgress = ref({ index: 0, total: 0, fileName: "", step: "" });
const fileInput = ref(null);

// Backend (flow/boot.py) is the single source of truth for supported file types.
const ACCEPT = computed(() =>
	(frappe.boot.flow_supported_file_types || []).map((ext) => `.${ext}`).join(","),
);

// "Uploaded" is no longer a transient state that resolves on its own — extraction
// only starts once the user confirms a Document Type on the detail page, so polling
// for it here would just poll forever. Only "Processing" (genuinely in-flight
// background work) needs to be watched.
const PENDING_STATUSES = new Set(["Processing"]);
const STATUS_THEME = {
	Uploaded: "gray",
	Processing: "blue",
	Extracted: "green",
	"Needs Review": "orange",
	Failed: "red",
	"Document Created": "green",
};

let pollTimer = null;

async function load() {
	entries.value = await listFile2ERPEntries();
	schedulePoll();
}

// Extraction runs in a background job; tell the user when one they're watching from
// this list finishes, so they don't have to keep an eye on the status column.
function notifyFinished(previous, current) {
	const wasPending = new Set(previous.filter((e) => PENDING_STATUSES.has(e.status)).map((e) => e.name));
	for (const entry of current) {
		if (!wasPending.has(entry.name) || PENDING_STATUSES.has(entry.status)) continue;
		const name = entry.file_name || entry.name;
		if (entry.status === "Failed") {
			frappe.show_alert({ message: __("Extraction failed for {0}.", [name]), indicator: "red" }, 7);
		} else if (entry.status === "Needs Review") {
			frappe.show_alert({ message: __("{0} extracted — needs review.", [name]), indicator: "orange" }, 7);
		} else {
			frappe.show_alert({ message: __("{0} extracted.", [name]), indicator: "green" }, 7);
		}
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

// Lightweight polling: while any entry is still Uploaded/Processing, refresh the list
// every few seconds so status updates (from the background extraction job) show up
// without the user having to reload the page.
function schedulePoll() {
	if (pollTimer) clearTimeout(pollTimer);
	if (!entries.value.some((e) => PENDING_STATUSES.has(e.status))) return;
	pollTimer = setTimeout(async () => {
		const previous = entries.value;
		entries.value = await listFile2ERPEntries();
		notifyFinished(previous, entries.value);
		schedulePoll();
	}, 3000);
}

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return entries.value;
	return entries.value.filter((e) => (e.file_name || "").toLowerCase().includes(q));
});

async function handleFiles(fileList) {
	const files = Array.from(fileList || []);
	if (!files.length) return;
	uploading.value = true;
	const created = [];
	try {
		for (const [index, file] of files.entries()) {
			uploadProgress.value = { index: index + 1, total: files.length, fileName: file.name, step: "upload" };
			try {
				const uploaded = await uploadFile(file);
				uploadProgress.value = { ...uploadProgress.value, step: "register" };
				const entry = await createFile2ERPEntry(uploaded.name);
				entries.value.unshift(entry);
				created.push(entry);
			} catch (e) {
				frappe.show_alert({
					message: e?.message || __("Could not process {0}.", [file.name]),
					indicator: "red",
				});
			}
		}
		schedulePoll();
		if (created.length) {
			frappe.show_alert({
				message:
					created.length === 1
						? __("Uploaded {0}. Choose a Document Type to extract its data.", [created[0].file_name])
						: __("Uploaded {0} files. Open each one to choose its Document Type and extract.", [created.length]),
				indicator: "green",
			});
		}
		// A single upload goes straight to its detail page to pick/confirm the Document
		// Type and start extraction — the whole point of showing that page at all. A
		// batch drop can't jump to more than one page at once, so it stays on the list;
		// each entry sits at "Uploaded" until opened individually.
		if (created.length === 1) {
			router.push({ name: "file2erp-detail", params: { name: created[0].name } });
		}
	} finally {
		uploading.value = false;
	}
}

function pickFiles() {
	fileInput.value?.click();
}
function onFilesPicked(e) {
	handleFiles(e.target.files);
	e.target.value = "";
}
function onDragOver(e) {
	e.preventDefault();
	dragging.value = true;
}
function onDragLeave(e) {
	if (e.currentTarget.contains(e.relatedTarget)) return;
	dragging.value = false;
}
function onDrop(e) {
	e.preventDefault();
	dragging.value = false;
	handleFiles(e.dataTransfer.files);
}

function openEntry(name) {
	router.push({ name: "file2erp-detail", params: { name } });
}

function removeEntry(entry, event) {
	event.stopPropagation();
	frappe.confirm(__('Delete "{0}"? This cannot be undone.', [entry.file_name || entry.name]), async () => {
		await deleteFile2ERPEntry(entry.name);
		entries.value = entries.value.filter((e) => e.name !== entry.name);
	});
}

function formatDate(ds) {
	return window.moment ? moment(ds).format("MMM D, YYYY h:mm A") : ds;
}
function formatSize(bytes) {
	if (!bytes) return "";
	const kb = bytes / 1024;
	return kb < 1024 ? `${kb.toFixed(0)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}
</script>

<template>
	<div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<h1 class="text-lg font-normal text-ink-gray-9">{{ __("File2ERP") }}</h1>
			<Button variant="solid" :loading="uploading" @click="pickFiles">
				<template #prefix><FeatherIcon name="upload" class="h-3.5 w-3.5" /></template>
				{{ __("Upload File") }}
			</Button>
			<input
				ref="fileInput"
				type="file"
				multiple
				:accept="ACCEPT"
				class="hidden"
				@change="onFilesPicked"
			/>
		</header>

		<div
			v-if="uploading"
			class="mx-6 mt-4 flex items-center gap-3 rounded-lg border border-outline-blue-1 bg-surface-blue-1 px-4 py-3 text-sm"
			role="status"
			aria-live="polite"
		>
			<Spinner class="h-4 w-4 shrink-0 text-ink-blue-3" />
			<span class="min-w-0 truncate text-ink-blue-3">
				<span v-if="uploadProgress.total > 1" class="font-medium">
					{{ __("{0} of {1}:", [uploadProgress.index, uploadProgress.total]) }}
				</span>
				{{
					uploadProgress.step === "register"
						? __("Preparing {0}…", [uploadProgress.fileName])
						: __("Uploading {0}…", [uploadProgress.fileName])
				}}
			</span>
		</div>

		<div class="px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search files…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div
			class="flow-scrollbar flex-1 overflow-y-auto px-6 pb-8"
			@dragover="onDragOver"
			@dragleave="onDragLeave"
			@drop="onDrop"
		>
			<div
				class="mb-4 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors"
				:class="dragging ? 'border-outline-gray-4 bg-surface-gray-1' : 'border-outline-gray-2'"
			>
				<FeatherIcon name="upload-cloud" class="h-6 w-6 text-ink-gray-4" />
				<p class="text-sm text-ink-gray-6">
					{{ __("Drag and drop files here, or") }}
					<button class="font-medium text-ink-blue-3 underline" @click="pickFiles">
						{{ __("browse") }}
					</button>
				</p>
				<p class="text-xs text-ink-gray-4">
					{{ __("PDF, images, Excel, Word, PowerPoint, CSV, and text files") }}
				</p>
			</div>

			<div v-if="loading" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>

			<div v-else-if="!filtered.length" class="py-16 text-center text-sm text-ink-gray-5">
				{{ query.trim() ? __("No matching files.") : __("No files uploaded yet.") }}
			</div>

			<div v-else class="overflow-x-auto rounded-lg border border-outline-gray-1">
				<table class="w-full min-w-max border-collapse text-sm">
					<thead>
						<tr class="border-b border-outline-gray-1 bg-surface-gray-1 text-left">
							<th class="px-3 py-2 text-xs font-medium text-ink-gray-6">{{ __("File") }}</th>
							<th class="px-3 py-2 text-xs font-medium text-ink-gray-6">{{ __("Type") }}</th>
							<th class="px-3 py-2 text-xs font-medium text-ink-gray-6">{{ __("Status") }}</th>
							<th class="px-3 py-2 text-xs font-medium text-ink-gray-6">{{ __("Document Type") }}</th>
							<th class="px-3 py-2 text-xs font-medium text-ink-gray-6">{{ __("Size") }}</th>
							<th class="px-3 py-2 text-xs font-medium text-ink-gray-6">{{ __("Uploaded") }}</th>
							<th class="w-8"></th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="entry in filtered"
							:key="entry.name"
							class="group cursor-pointer border-b border-outline-gray-1 last:border-0 hover:bg-surface-gray-1"
							@click="openEntry(entry.name)"
						>
							<td class="max-w-xs truncate px-3 py-2 font-medium text-ink-gray-9">
								{{ entry.file_name }}
							</td>
							<td class="px-3 py-2 text-ink-gray-6">{{ entry.file_type }}</td>
							<td class="px-3 py-2">
								<div class="flex items-center gap-1.5">
									<Spinner
										v-if="PENDING_STATUSES.has(entry.status)"
										class="h-3.5 w-3.5 text-ink-blue-3"
									/>
									<Badge
										variant="subtle"
										:theme="STATUS_THEME[entry.status] || 'gray'"
										:label="__(entry.status)"
									/>
								</div>
							</td>
							<td class="px-3 py-2 text-ink-gray-6">{{ entry.document_type || "—" }}</td>
							<td class="px-3 py-2 text-ink-gray-6">{{ formatSize(entry.file_size) }}</td>
							<td class="px-3 py-2 text-ink-gray-6">{{ formatDate(entry.creation) }}</td>
							<td class="px-1 py-2">
								<button
									class="flex h-6 w-6 items-center justify-center rounded text-ink-gray-4 opacity-0 hover:bg-surface-gray-2 hover:text-ink-red-4 group-hover:opacity-100"
									:title="__('Delete')"
									@click="removeEntry(entry, $event)"
								>
									<FeatherIcon name="trash-2" class="h-3.5 w-3.5" />
								</button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>
