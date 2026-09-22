<script setup>
// Trusted first-party File URL (a Flow File2ERP entry's own attachment) — a plain
// <iframe>/<img> is enough, no viewer library needed. Word/Excel files are rendered
// to PDF server-side (LibreOffice) and shown in the same iframe.
import { computed, ref, watch, nextTick, onBeforeUnmount } from "vue";
import { FeatherIcon } from "@/lib/ui";
import { __ } from "@/lib/translate";

const props = defineProps({
	fileUrl: { type: String, default: "" },
	fileName: { type: String, default: "" },
	entryName: { type: String, default: "" },
});

const DOCX_EXTENSIONS = ["docx"];
const SHEET_EXTENSIONS = ["xls", "xlsx"];
// Legacy binary .doc has no browser-side renderer, so it falls back to a server-side PDF.
const LEGACY_OFFICE_EXTENSIONS = ["doc"];
const MAX_SHEET_ROWS = 2000;
const IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif"];

const extension = computed(() => (props.fileName.split(".").pop() || "").toLowerCase());
const officePreviewUrl = computed(
	() => `/api/method/flow.api.file2erp.preview_file2erp_file?name=${encodeURIComponent(props.entryName)}`
);
const kind = computed(() => {
	if (extension.value === "pdf") return "pdf";
	if (DOCX_EXTENSIONS.includes(extension.value) && props.fileUrl) return "docx";
	if (SHEET_EXTENSIONS.includes(extension.value) && props.fileUrl) return "sheet";
	if (LEGACY_OFFICE_EXTENSIONS.includes(extension.value) && props.entryName) return "office";
	if (IMAGE_EXTENSIONS.includes(extension.value)) return "image";
	return "other";
});

// Read-only in-browser rendering of the original document (no editing surface exists).
const docxEl = ref(null);
const loading = ref(false);
const loadError = ref("");
const sheets = ref([]);
const activeSheet = ref(0);
const truncated = ref(false);
let loadToken = 0;

async function fetchBlob() {
	const res = await fetch(props.fileUrl, { credentials: "same-origin" });
	if (!res.ok) throw new Error(res.statusText);
	return res.blob();
}

async function renderDocx(token) {
	const [{ renderAsync }, blob] = await Promise.all([import("docx-preview"), fetchBlob()]);
	await nextTick();
	if (token !== loadToken || !docxEl.value) return;
	docxEl.value.innerHTML = "";
	await renderAsync(blob, docxEl.value, null, { inWrapper: true, ignoreLastRenderedPageBreak: true });
}

async function renderSheets(token) {
	const [XLSX, blob] = await Promise.all([import("xlsx"), fetchBlob()]);
	const wb = XLSX.read(await blob.arrayBuffer(), { type: "array" });
	if (token !== loadToken) return;
	truncated.value = false;
	sheets.value = wb.SheetNames.map((name) => {
		const rows = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, defval: "", raw: false });
		if (rows.length > MAX_SHEET_ROWS) truncated.value = true;
		return { name, rows: rows.slice(0, MAX_SHEET_ROWS) };
	});
	activeSheet.value = 0;
}

watch(
	[kind, () => props.fileUrl],
	async ([k]) => {
		const token = ++loadToken;
		loadError.value = "";
		sheets.value = [];
		if (k !== "docx" && k !== "sheet") return;
		loading.value = true;
		try {
			await (k === "docx" ? renderDocx(token) : renderSheets(token));
		} catch (e) {
			if (token === loadToken) loadError.value = __("Could not load a preview for this file.");
		} finally {
			if (token === loadToken) loading.value = false;
		}
	},
	{ immediate: true }
);
onBeforeUnmount(() => loadToken++);
</script>

<template>
	<div class="flex h-full min-h-0 flex-col items-center justify-center overflow-hidden bg-surface-gray-1">
		<iframe v-if="kind === 'pdf' && fileUrl" :src="fileUrl" class="h-full w-full border-0" :title="fileName" />
		<div v-else-if="(kind === 'docx' || kind === 'sheet') && loadError" class="flex flex-col items-center gap-3 p-8 text-center">
			<FeatherIcon name="file" class="h-10 w-10 text-ink-gray-4" />
			<p class="text-sm text-ink-gray-6">{{ loadError }}</p>
			<a :href="fileUrl" target="_blank" rel="noopener noreferrer" class="text-sm font-medium text-ink-blue-3 underline">
				{{ __("Download {0}", [fileName]) }}
			</a>
		</div>
		<template v-else-if="kind === 'docx'">
			<p v-if="loading" class="text-sm text-ink-gray-5">{{ __("Loading preview…") }}</p>
			<div ref="docxEl" class="flow-scrollbar-visible h-full w-full select-text overflow-auto" :class="{ hidden: loading }" />
		</template>
		<p v-else-if="kind === 'sheet' && loading" class="text-sm text-ink-gray-5">{{ __("Loading preview…") }}</p>
		<div v-else-if="kind === 'sheet' && !loadError && sheets.length" class="flex h-full min-h-0 w-full min-w-0 flex-col bg-surface-white">
			<div class="flow-scrollbar-visible min-h-0 min-w-0 flex-1 overflow-auto">
				<table class="w-max border-collapse text-xs text-ink-gray-8">
					<tbody>
						<tr v-for="(row, r) in sheets[activeSheet].rows" :key="r">
							<td
								v-for="(cell, c) in row"
								:key="c"
								class="max-w-[320px] truncate border border-outline-gray-2 px-2 py-1 whitespace-nowrap"
							>{{ cell }}</td>
						</tr>
					</tbody>
				</table>
				<p v-if="truncated" class="p-2 text-xs text-ink-gray-5">{{ __("Showing the first {0} rows of each sheet.", [2000]) }}</p>
			</div>
			<div v-if="sheets.length > 1" class="flex shrink-0 gap-1 overflow-x-auto border-t border-outline-gray-2 bg-surface-gray-1 px-2 py-1">
				<button
					v-for="(sheet, i) in sheets"
					:key="sheet.name"
					class="whitespace-nowrap rounded px-2 py-1 text-xs"
					:class="i === activeSheet ? 'bg-surface-white font-medium text-ink-gray-9 shadow-sm' : 'text-ink-gray-6'"
					@click="activeSheet = i"
				>{{ sheet.name }}</button>
			</div>
		</div>
		<iframe v-else-if="kind === 'office'" :src="officePreviewUrl" class="h-full w-full border-0" :title="fileName" />
		<img
			v-else-if="kind === 'image' && fileUrl"
			:src="fileUrl"
			:alt="fileName"
			class="max-h-full max-w-full object-contain"
		/>
		<div v-else class="flex flex-col items-center gap-3 p-8 text-center">
			<FeatherIcon name="file" class="h-10 w-10 text-ink-gray-4" />
			<p class="text-sm text-ink-gray-6">{{ __("No preview available for this file type.") }}</p>
			<a
				v-if="fileUrl"
				:href="fileUrl"
				target="_blank"
				rel="noopener noreferrer"
				class="text-sm font-medium text-ink-blue-3 underline"
			>
				{{ __("Download {0}", [fileName]) }}
			</a>
		</div>
	</div>
</template>
