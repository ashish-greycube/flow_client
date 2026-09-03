<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PanelDropdown from "@/components/PanelDropdown.vue";
import DocSection from "@/components/DocSection.vue";
import { Button, FeatherIcon, Spinner, Badge, TextInput, Textarea, Switch, Breadcrumbs } from "@/lib/ui";
import { __ } from "@/lib/translate";
import {
	getKnowledgeBase,
	getKnowledgeSource,
	createKnowledgeSource,
	saveKnowledgeSource,
	resyncKnowledgeSource,
	reconcileKnowledgeSource,
	loadReferenceDoctypes,
	uploadFile,
} from "@/api/client";

// Full page for both Create and Edit (routed at
// /knowledge-bases/:name/sources/new and .../sources/:source). Styled like
// AgentFormView.vue (Breadcrumbs, title/"Not Saved" badge, DocSections), but
// unlike Agent/Knowledge Base it does NOT redirect to a list after Save — a
// new source instead lands on its own saved edit route (mirrors Jarvis's
// MacroDetail isNew→saved transition), because Resync/Reconcile and the
// chunking-changed rebuild prompt only make sense once the doc actually
// exists, exactly as flow_knowledge_source.js's frm.call()/after_save do.
const route = useRoute();
const router = useRouter();

const kbName = computed(() => route.params.name);
const sourceName = computed(() => route.params.source || null);
const isEdit = computed(() => !!sourceName.value);

const SOURCE_TYPE_ITEMS = [
	{ value: "Text", label: __("Text") },
	{ value: "File", label: __("File") },
	{ value: "URL", label: __("URL") },
	{ value: "DocType", label: __("DocType") },
];

const loading = ref(false);
const saving = ref(false);
const resyncing = ref(false);
const reconciling = ref(false);
const uploading = ref(false);
const kbTitle = ref("");
const referenceDoctypes = ref([]);
const fileInput = ref(null);
// Flow Knowledge Source only blocks delete for built-in sources
// (flow_knowledge_source.py's on_trash → block_delete) — source_type and
// knowledge_base are locked on ANY existing source regardless (see the
// :disabled="isEdit" below), not just system-generated ones.
const isSystemGenerated = ref(false);
// Baseline for the "chunking changed, rebuild?" prompt — set once on load,
// compared against the values actually sent on the next save.
const chunkingBaseline = ref(null);
const priorChunkCount = ref(0);
// frappe.client.save reconstructs the doc from scratch (frappe.get_doc(dict)),
// not by loading + merging onto the DB row — so any standard field it omits
// reads as empty on the new in-memory doc. `modified` has to be the real DB
// value or Document.check_if_latest() throws TimestampMismatchError (it
// compares against empty, which never matches); `creation`/`owner` have to be
// the real values too or validate_set_only_once() throws "Value cannot be
// changed for Created On" — creation/owner are unconditionally set-only-once
// for every doctype (frappe/model/meta.py's standard_set_once_fields).
// Refreshed on every load(), which this view always re-runs after a save,
// resync, or reconcile — each of those touches the doc's own modified too.
const docMeta = ref({ modified: null, creation: null, owner: null });

const form = reactive({
	title: "",
	source_type: "Text",
	content: "",
	file: "",
	url: "",
	reference_doctype: null,
	filters: "",
	content_fields: "",
	auto_sync: false,
	chunk_size: 0,
	chunk_overlap: 0,
	status: "Pending",
	chunk_count: 0,
	last_synced_at: "",
	error_log: "",
});
const snapshot = ref(null);

const referenceDoctypeItems = computed(() => referenceDoctypes.value.map((d) => ({ value: d.name, label: d.name })));
const acceptFileTypes = computed(() =>
	(frappe.boot.flow_supported_file_types || []).map((ext) => `.${ext}`).join(",")
);

const canSave = computed(() => {
	if (!form.title.trim() || saving.value) return false;
	if (form.source_type === "Text") return !!form.content.trim();
	if (form.source_type === "File") return !!form.file;
	if (form.source_type === "URL") return !!form.url.trim();
	if (form.source_type === "DocType") return !!form.reference_doctype && !!form.content_fields.trim();
	return false;
});

const dirty = computed(() => {
	const snap = snapshot.value;
	if (!snap || loading.value) return false;
	return (
		(form.title || "") !== snap.title ||
		form.source_type !== snap.source_type ||
		(form.content || "") !== snap.content ||
		(form.file || "") !== snap.file ||
		(form.url || "") !== snap.url ||
		(form.reference_doctype || null) !== snap.reference_doctype ||
		(form.filters || "") !== snap.filters ||
		(form.content_fields || "") !== snap.content_fields ||
		(form.auto_sync ? 1 : 0) !== snap.auto_sync ||
		Number(form.chunk_size || 0) !== snap.chunk_size ||
		Number(form.chunk_overlap || 0) !== snap.chunk_overlap
	);
});

const pageTitle = computed(() =>
	isEdit.value ? form.title || sourceName.value : form.title || __("New Source")
);
const breadcrumbs = computed(() => [
	{ label: __("Knowledge Base"), route: { name: "knowledge-bases" } },
	{
		label: kbTitle.value || kbName.value,
		route: { name: "knowledge-base-edit", params: { name: kbName.value } },
	},
	isEdit.value
		? {
				label: pageTitle.value,
				route: { name: "knowledge-source-edit", params: { name: kbName.value, source: sourceName.value } },
			}
		: { label: __("New Source"), route: { name: "knowledge-source-new", params: { name: kbName.value } } },
]);

function snapshotForm() {
	snapshot.value = {
		title: form.title,
		source_type: form.source_type,
		content: form.content,
		file: form.file,
		url: form.url,
		reference_doctype: form.reference_doctype,
		filters: form.filters,
		content_fields: form.content_fields,
		auto_sync: form.auto_sync ? 1 : 0,
		chunk_size: Number(form.chunk_size || 0),
		chunk_overlap: Number(form.chunk_overlap || 0),
	};
}

function fileName(url) {
	return (url || "").split("/").pop();
}

function statusTheme(status) {
	if (status === "Completed") return "green";
	if (status === "Failed") return "red";
	if (status === "Processing") return "orange";
	return "gray";
}

function formatDatetime(value) {
	if (!value) return __("Never");
	return window.moment ? moment(value).format("MMM D, YYYY h:mm A") : value;
}

async function load() {
	[kbTitle.value, referenceDoctypes.value] = await Promise.all([
		getKnowledgeBase(kbName.value)
			.then((doc) => doc.title)
			.catch(() => ""),
		loadReferenceDoctypes().catch(() => []),
	]);

	if (isEdit.value) {
		loading.value = true;
		try {
			const doc = await getKnowledgeSource(sourceName.value);
			form.title = doc.title || "";
			form.source_type = doc.source_type || "Text";
			form.content = doc.content || "";
			form.file = doc.file || "";
			form.url = doc.url || "";
			form.reference_doctype = doc.reference_doctype || null;
			form.filters = doc.filters || "";
			form.content_fields = doc.content_fields || "";
			form.auto_sync = !!doc.auto_sync;
			form.chunk_size = doc.chunk_size || 0;
			form.chunk_overlap = doc.chunk_overlap || 0;
			form.status = doc.status || "Pending";
			form.chunk_count = doc.chunk_count || 0;
			form.last_synced_at = doc.last_synced_at || "";
			form.error_log = doc.error_log || "";
			isSystemGenerated.value = !!doc.is_system_generated;
			docMeta.value = { modified: doc.modified, creation: doc.creation, owner: doc.owner };
			chunkingBaseline.value = { chunk_size: form.chunk_size, chunk_overlap: form.chunk_overlap };
			priorChunkCount.value = form.chunk_count;
		} catch (e) {
			frappe.show_alert({ message: e.message || __("Could not load source."), indicator: "red" });
			goBack();
			return;
		} finally {
			loading.value = false;
		}
	} else {
		form.title = "";
		form.source_type = "Text";
		form.content = "";
		form.file = "";
		form.url = "";
		form.reference_doctype = null;
		form.filters = "";
		form.content_fields = "";
		form.auto_sync = false;
		form.chunk_size = 0;
		form.chunk_overlap = 0;
	}
	snapshotForm();
}
// A watcher, not onMounted: creating a source navigates via router.replace
// from knowledge-source-new to knowledge-source-edit for the SAME name/source
// route params it's about to receive — since both routes resolve to this one
// component, vue-router reuses the existing instance rather than remounting
// it (unlike Agent/Knowledge Base, which always leave this form after a
// create), so onMounted would never fire again and docMeta would stay at its
// null default for the very next save. Mirrors Jarvis's own MacroDetail.vue
// (watch(() => [props.id, props.isNew], init, { immediate: true })), which
// this codebase's own MacroView.vue actually diverged from by using
// onMounted — the same latent bug, just not yet hit there.
watch(() => [kbName.value, sourceName.value], load, { immediate: true });

function goBack() {
	router.push({ name: "knowledge-base-edit", params: { name: kbName.value } });
}

async function onFilePicked(e) {
	const file = e.target.files?.[0];
	e.target.value = "";
	if (!file) return;
	uploading.value = true;
	try {
		const result = await uploadFile(file);
		form.file = result.file_url;
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Upload failed."), indicator: "red" });
	} finally {
		uploading.value = false;
	}
}

// The `filters` column has a MySQL JSON CHECK constraint — an empty string
// isn't valid JSON (unlike an empty Long Text field), so "no filters" has to
// be `null`, never "".
function parseFiltersOrThrow() {
	const raw = (form.filters || "").trim();
	if (!raw) return null;
	try {
		JSON.parse(raw);
		return raw;
	} catch {
		throw new Error(__("Filters must be valid JSON."));
	}
}

async function save() {
	if (!canSave.value) return;
	if (
		form.chunk_size &&
		form.chunk_overlap &&
		Number(form.chunk_overlap) >= Number(form.chunk_size)
	) {
		frappe.show_alert({
			message: __("Chunk Overlap must be smaller than Chunk Size."),
			indicator: "red",
		});
		return;
	}
	let filtersValue;
	try {
		filtersValue = parseFiltersOrThrow();
	} catch (e) {
		frappe.show_alert({ message: e.message, indicator: "red" });
		return;
	}

	saving.value = true;
	try {
		const isDocType = form.source_type === "DocType";
		const values = {
			title: form.title.trim(),
			source_type: form.source_type,
			content: form.source_type === "Text" ? form.content : "",
			file: form.source_type === "File" ? form.file : "",
			url: form.source_type === "URL" ? form.url.trim() : "",
			reference_doctype: isDocType ? form.reference_doctype : null,
			filters: isDocType ? filtersValue : null,
			content_fields: isDocType ? form.content_fields.trim() : "",
			auto_sync: isDocType && form.auto_sync ? 1 : 0,
			chunk_size: Number(form.chunk_size || 0),
			chunk_overlap: Number(form.chunk_overlap || 0),
		};
		if (isEdit.value) {
			await saveKnowledgeSource({
				name: sourceName.value,
				knowledge_base: kbName.value,
				...docMeta.value,
				is_system_generated: isSystemGenerated.value ? 1 : 0,
				...values,
			});
			frappe.show_alert({ message: __("Source updated."), indicator: "green" });

			const changed =
				chunkingBaseline.value &&
				(chunkingBaseline.value.chunk_size !== values.chunk_size ||
					chunkingBaseline.value.chunk_overlap !== values.chunk_overlap);
			if (changed && priorChunkCount.value) {
				frappe.confirm(
					__(
						"Chunk settings changed. The {0} existing chunks for this source will be deleted and rebuilt with the new settings. Re-process now?",
						[priorChunkCount.value]
					),
					() => {
						resyncKnowledgeSource(sourceName.value, true).then(() => {
							frappe.show_alert({ message: __("Re-ingestion started"), indicator: "blue" });
							load();
						});
					}
				);
			} else {
				await load();
			}
		} else {
			const created = await createKnowledgeSource({ knowledge_base: kbName.value, ...values });
			frappe.show_alert({ message: __("Source created."), indicator: "green" });
			router.replace({
				name: "knowledge-source-edit",
				params: { name: kbName.value, source: created.name },
			});
		}
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Could not save source."), indicator: "red" });
	} finally {
		saving.value = false;
	}
}

async function resync() {
	resyncing.value = true;
	try {
		await resyncKnowledgeSource(sourceName.value, false);
		frappe.show_alert({ message: __("Resync started"), indicator: "blue" });
		await load();
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Could not start resync."), indicator: "red" });
	} finally {
		resyncing.value = false;
	}
}

async function reconcile() {
	reconciling.value = true;
	try {
		await reconcileKnowledgeSource(sourceName.value);
		frappe.show_alert({ message: __("Reconcile started"), indicator: "blue" });
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Could not start reconcile."), indicator: "red" });
	} finally {
		reconciling.value = false;
	}
}
</script>

<template>
	<div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<Breadcrumbs class="form-breadcrumbs" :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<Button v-if="isEdit" variant="subtle" :loading="resyncing" @click="resync">{{
					__("Resync")
				}}</Button>
				<Button
					v-if="isEdit && form.source_type === 'DocType'"
					variant="subtle"
					:loading="reconciling"
					@click="reconcile"
					>{{ __("Reconcile") }}</Button
				>
				<Button variant="subtle" :disabled="saving" @click="goBack">{{ __("Cancel") }}</Button>
				<Button variant="solid" :disabled="!canSave || !dirty" :loading="saving" @click="save">{{
					isEdit ? __("Save") : __("Create Source")
				}}</Button>
			</div>
		</header>

		<div v-if="loading" class="flex justify-center py-16">
			<Spinner class="h-5 w-5 text-ink-gray-5" />
		</div>

		<div v-else class="flow-scrollbar flex-1 overflow-y-auto px-6 py-6">
			<div class="mx-auto max-w-3xl">
				<div class="flex items-center gap-3">
					<h1 class="min-w-0 truncate text-2xl font-semibold text-ink-gray-9">
						{{ pageTitle }}
					</h1>
					<Badge v-if="dirty" variant="subtle" theme="orange" :label="__('Not Saved')" />
				</div>

				<div class="mt-4">
					<DocSection :label="__('Details')" :collapsible="false">
						<div class="space-y-4">
							<TextInput
								type="text"
								:label="__('Title')"
								:placeholder="__('e.g. Refund Policy')"
								:model-value="form.title"
								:disabled="saving"
								@update:model-value="(v) => (form.title = v)"
							/>

							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{ __("Knowledge Base") }}</label>
								<div
									class="flex h-8 w-full items-center rounded-md border border-outline-gray-2 bg-surface-gray-1 px-2.5 text-sm text-ink-gray-5"
								>
									{{ kbTitle || kbName }}
								</div>
							</div>

							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{ __("Source Type") }}</label>
								<PanelDropdown
									:items="SOURCE_TYPE_ITEMS"
									:model-value="form.source_type"
									:disabled="isEdit || saving"
									placement="bottom"
									match-trigger-width
									@update:model-value="(v) => (form.source_type = v)"
								>
									<template #trigger="{ toggle }">
										<button
											class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2 disabled:bg-surface-gray-1"
											:class="{ 'cursor-not-allowed opacity-70': isEdit }"
											@click="toggle"
										>
											<span class="truncate">{{
												SOURCE_TYPE_ITEMS.find((i) => i.value === form.source_type)?.label
											}}</span>
											<FeatherIcon
												name="chevron-down"
												class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
											/>
										</button>
									</template>
								</PanelDropdown>
								<p v-if="isEdit" class="mt-1 text-xs text-ink-gray-5">
									{{ __("Source type can't be changed after creation.") }}
								</p>
							</div>
						</div>
					</DocSection>

					<DocSection :label="__('Source')" :collapsible="false">
						<div class="space-y-4">
							<Textarea
								v-if="form.source_type === 'Text'"
								:label="__('Content')"
								:rows="8"
								:placeholder="__('Paste or write the text this source indexes.')"
								:model-value="form.content"
								:disabled="saving"
								@update:model-value="(v) => (form.content = v)"
							/>

							<div v-else-if="form.source_type === 'File'">
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{ __("File") }}</label>
								<div class="flex items-center gap-2">
									<input
										ref="fileInput"
										type="file"
										class="hidden"
										:accept="acceptFileTypes"
										@change="onFilePicked"
									/>
									<Button variant="subtle" :loading="uploading" @click="fileInput.click()">{{
										form.file ? __("Replace file") : __("Choose file")
									}}</Button>
									<span v-if="form.file" class="truncate text-sm text-ink-gray-7">{{
										fileName(form.file)
									}}</span>
									<button
										v-if="form.file"
										class="text-ink-gray-5 hover:text-ink-gray-8"
										:title="__('Remove')"
										@click="form.file = ''"
									>
										<FeatherIcon name="x" class="h-3.5 w-3.5" />
									</button>
								</div>
							</div>

							<TextInput
								v-else-if="form.source_type === 'URL'"
								type="url"
								:label="__('URL')"
								placeholder="https://example.com/doc"
								:model-value="form.url"
								:disabled="saving"
								@update:model-value="(v) => (form.url = v)"
							/>

							<template v-else-if="form.source_type === 'DocType'">
								<div>
									<label class="mb-1.5 block text-xs text-ink-gray-5">{{
										__("Reference DocType")
									}}</label>
									<PanelDropdown
										:items="referenceDoctypeItems"
										:model-value="form.reference_doctype"
										:disabled="saving"
										placement="bottom"
										searchable
										match-trigger-width
										@update:model-value="(v) => (form.reference_doctype = v)"
									>
										<template #trigger="{ toggle }">
											<button
												class="flex h-8 w-full items-center justify-between rounded-md border border-outline-gray-2 px-2.5 text-left text-sm font-normal text-ink-gray-9 hover:bg-surface-gray-2"
												@click="toggle"
											>
												<span class="truncate">{{
													form.reference_doctype || __("Select a DocType")
												}}</span>
												<FeatherIcon
													name="chevron-down"
													class="h-3.5 w-3.5 shrink-0 text-ink-gray-5"
												/>
											</button>
										</template>
									</PanelDropdown>
								</div>

								<TextInput
									type="text"
									:label="__('Content Fields')"
									:placeholder="__('e.g. subject, description, resolution')"
									:model-value="form.content_fields"
									:disabled="saving"
									:description="
										__('Comma-separated fieldnames whose values are indexed.')
									"
									@update:model-value="(v) => (form.content_fields = v)"
								/>

								<Textarea
									:label="__('Filters')"
									:rows="3"
									placeholder='{&quot;status&quot;: &quot;Resolved&quot;}'
									:model-value="form.filters"
									:disabled="saving"
									:description="
										__('Optional JSON filters selecting which documents to index.')
									"
									@update:model-value="(v) => (form.filters = v)"
								/>

								<Switch
									v-model="form.auto_sync"
									:label="__('Auto Sync')"
									:description="__('Keep this source in sync with a daily incremental sweep.')"
									:disabled="saving"
								/>
							</template>
						</div>
					</DocSection>

					<DocSection :label="__('Chunking')" :collapsible="false">
						<div class="grid grid-cols-2 gap-4">
							<TextInput
								type="number"
								:label="__('Chunk Size')"
								placeholder="0"
								:model-value="form.chunk_size"
								:disabled="saving"
								:description="__('Leave 0 to inherit the global default.')"
								@update:model-value="(v) => (form.chunk_size = v === '' ? 0 : Number(v))"
							/>
							<TextInput
								type="number"
								:label="__('Chunk Overlap')"
								placeholder="0"
								:model-value="form.chunk_overlap"
								:disabled="saving"
								:description="__('Leave 0 to inherit the global default.')"
								@update:model-value="(v) => (form.chunk_overlap = v === '' ? 0 : Number(v))"
							/>
						</div>
					</DocSection>

					<DocSection v-if="isEdit" :label="__('Indexing')" :collapsible="false">
						<div class="grid grid-cols-3 gap-4">
							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{ __("Status") }}</label>
								<Badge variant="subtle" :theme="statusTheme(form.status)" :label="form.status" />
							</div>
							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{ __("Chunk Count") }}</label>
								<div class="text-sm text-ink-gray-8">{{ form.chunk_count }}</div>
							</div>
							<div>
								<label class="mb-1.5 block text-xs text-ink-gray-5">{{
									__("Last Synced At")
								}}</label>
								<div class="text-sm text-ink-gray-8">{{ formatDatetime(form.last_synced_at) }}</div>
							</div>
						</div>
					</DocSection>

					<DocSection v-if="isEdit && form.error_log" :label="__('Error')" :collapsible="false">
						<pre
							class="whitespace-pre-wrap rounded-md border border-outline-gray-1 bg-surface-gray-1 p-3 text-xs text-ink-red-2"
							>{{ form.error_log }}</pre
						>
					</DocSection>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
/* Breadcrumbs' crumb links render at text-lg (17px in this app's Tailwind
   fontSize scale) — no smaller size prop exists, so this has to target the
   rendered <a>/<button> tags directly. */
.form-breadcrumbs :deep(a),
.form-breadcrumbs :deep(button) {
	font-size: 15px !important;
}
</style>
