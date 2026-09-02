<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DocSection from "@/components/DocSection.vue";
import { Button, FeatherIcon, Spinner, Badge, TextInput, Textarea, Switch, Breadcrumbs } from "@/lib/ui";
import { __ } from "@/lib/translate";
import {
	getKnowledgeBase,
	createKnowledgeBase,
	saveKnowledgeBase,
	renameKnowledgeBase,
	loadKnowledgeSources,
} from "@/api/client";

// Full page for both Create and Edit (routed at /knowledge-bases/new and
// /knowledge-bases/:name) — styled identically to AgentFormView.vue (same
// Breadcrumbs + title/"Not Saved" badge + DocSection layout), per the user's
// "keep it like agent pages" instruction. The "Knowledge Sources" section is
// this doctype's own Desk "Connections" tab equivalent — Flow Knowledge
// Source links back via its `knowledge_base` field, it has no field on Flow
// Knowledge Base itself.
const route = useRoute();
const router = useRouter();

const kbName = computed(() => route.params.name || null);
const isEdit = computed(() => !!kbName.value);

const loading = ref(false);
const saving = ref(false);
const sources = ref([]);
const loadingSources = ref(false);
// Flow Knowledge Base is `autoname: "field:title"` — same title/rename lock
// as Flow Agent (see AgentFormView.vue's note): the title field re-syncs to
// the docname on every save, and renames are blocked outright for built-in
// (is_system_generated) knowledge bases.
const isSystemGenerated = ref(false);
// frappe.client.save reconstructs the doc from scratch (frappe.get_doc(dict)),
// not by loading + merging onto the DB row — so any standard field it omits
// reads as empty on the new in-memory doc. `modified` has to be the real DB
// value or Document.check_if_latest() throws TimestampMismatchError (it
// compares against empty, which never matches); `creation`/`owner` have to be
// the real values too or validate_set_only_once() throws "Value cannot be
// changed for Created On" — creation/owner are unconditionally set-only-once
// for every doctype (frappe/model/meta.py's standard_set_once_fields).
const docMeta = ref({ modified: null, creation: null, owner: null });

const form = reactive({
	title: "",
	enabled: true,
	description: "",
});
const snapshot = ref(null);

const canSave = computed(() => form.title.trim() && !saving.value);

const dirty = computed(() => {
	const snap = snapshot.value;
	if (!snap || loading.value) return false;
	return (
		(form.title || "") !== snap.title ||
		(form.enabled ? 1 : 0) !== snap.enabled ||
		(form.description || "") !== snap.description
	);
});

const pageTitle = computed(() =>
	isEdit.value ? form.title || kbName.value : form.title || __("New Knowledge Base")
);
const breadcrumbs = computed(() => [
	{ label: __("Knowledge Base"), route: { name: "knowledge-bases" } },
	isEdit.value
		? {
				label: pageTitle.value,
				route: { name: "knowledge-base-edit", params: { name: kbName.value } },
			}
		: { label: __("New Knowledge Base"), route: { name: "knowledge-base-new" } },
]);

function snapshotForm() {
	snapshot.value = {
		title: form.title,
		enabled: form.enabled ? 1 : 0,
		description: form.description,
	};
}

async function loadSources() {
	if (!isEdit.value) return;
	loadingSources.value = true;
	try {
		sources.value = await loadKnowledgeSources(kbName.value);
	} catch {
		sources.value = [];
	} finally {
		loadingSources.value = false;
	}
}

async function load() {
	if (isEdit.value) {
		loading.value = true;
		try {
			const doc = await getKnowledgeBase(kbName.value);
			form.title = doc.title || "";
			form.enabled = !!doc.enabled;
			form.description = doc.description || "";
			isSystemGenerated.value = !!doc.is_system_generated;
			docMeta.value = { modified: doc.modified, creation: doc.creation, owner: doc.owner };
		} catch (e) {
			frappe.show_alert({ message: e.message || __("Could not load knowledge base."), indicator: "red" });
			goBack();
			return;
		} finally {
			loading.value = false;
		}
		await loadSources();
	} else {
		form.title = "";
		form.enabled = true;
		form.description = "";
		sources.value = [];
	}
	snapshotForm();
}
// A watcher, not onMounted: after Save this view now stays on the knowledge
// base's own page instead of bouncing to the list, which for a fresh create
// means routing from knowledge-base-new to knowledge-base-edit for the SAME
// name it's about to receive — since both routes resolve to this one
// component, vue-router reuses the existing instance rather than remounting
// it, so onMounted would never fire again (see AgentFormView.vue's identical
// fix/note).
watch(kbName, load, { immediate: true });

function goBack() {
	router.push({ name: "knowledge-bases" });
}

async function save() {
	if (!canSave.value) return;
	saving.value = true;
	try {
		const values = {
			enabled: form.enabled ? 1 : 0,
			description: form.description.trim(),
		};
		let finalName;
		if (isEdit.value) {
			let name = kbName.value;
			const newTitle = form.title.trim();
			if (!isSystemGenerated.value && newTitle !== name) {
				name = await renameKnowledgeBase(name, newTitle);
				// The rename itself touches the doc, so `modified` captured at load
				// time is now stale — refetch or the save below throws
				// TimestampMismatchError against the post-rename row.
				const fresh = await getKnowledgeBase(name);
				docMeta.value = { modified: fresh.modified, creation: fresh.creation, owner: fresh.owner };
			}
			await saveKnowledgeBase({
				name,
				title: name,
				...docMeta.value,
				is_system_generated: isSystemGenerated.value ? 1 : 0,
				...values,
			});
			frappe.show_alert({ message: __("Knowledge base updated."), indicator: "green" });
			finalName = name;
		} else {
			const created = await createKnowledgeBase({ title: form.title.trim(), ...values });
			frappe.show_alert({ message: __("Knowledge base created."), indicator: "green" });
			finalName = created.name;
		}
		// Stay on the knowledge base's own page after saving instead of
		// bouncing back to the list. A rename changed the docname, so the
		// route has to follow it (the watcher above then reloads under the
		// new name); otherwise just reload in place to clear the dirty badge
		// and refresh docMeta.
		if (kbName.value !== finalName) {
			await router.replace({ name: "knowledge-base-edit", params: { name: finalName } });
		} else {
			await load();
		}
	} catch (e) {
		frappe.show_alert({ message: e.message || __("Could not save knowledge base."), indicator: "red" });
	} finally {
		saving.value = false;
	}
}

function statusTheme(status) {
	if (status === "Completed") return "bg-surface-green-2 text-ink-green-2";
	if (status === "Failed") return "bg-surface-red-2 text-ink-red-2";
	if (status === "Processing") return "bg-surface-orange-2 text-ink-orange-2";
	return "bg-surface-gray-2 text-ink-gray-6";
}

function openSource(source) {
	router.push({ name: "knowledge-source-edit", params: { name: kbName.value, source } });
}

function newSource() {
	router.push({ name: "knowledge-source-new", params: { name: kbName.value } });
}
</script>

<template>
	<div class="relative flex min-w-0 flex-1 flex-col bg-surface-white text-ink-gray-9">
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<Breadcrumbs class="form-breadcrumbs" :items="breadcrumbs" />
			<div class="flex items-center gap-2">
				<Button variant="subtle" :disabled="saving" @click="goBack">{{ __("Cancel") }}</Button>
				<Button variant="solid" :disabled="!canSave || !dirty" :loading="saving" @click="save">{{
					isEdit ? __("Save") : __("Create Knowledge Base")
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
								:placeholder="__('e.g. Support Docs')"
								:model-value="form.title"
								:disabled="isSystemGenerated || saving"
								:description="isSystemGenerated ? __('Built-in knowledge bases can\'t be renamed.') : ''"
								@update:model-value="(v) => (form.title = v)"
							/>

							<Textarea
								:label="__('Description')"
								:rows="3"
								:placeholder="__('What kind of knowledge does this base hold?')"
								:model-value="form.description"
								:disabled="saving"
								@update:model-value="(v) => (form.description = v)"
							/>

							<Switch
								v-model="form.enabled"
								:label="__('Enabled')"
								:description="__('Off = hidden from agent Knowledge Base pickers.')"
								:disabled="saving"
							/>
						</div>
					</DocSection>

					<DocSection v-if="isEdit" :label="__('Knowledge Sources')" :collapsible="false">
						<div class="flex flex-col gap-2">
							<div v-if="loadingSources" class="flex justify-center py-6">
								<Spinner class="h-4 w-4 text-ink-gray-5" />
							</div>

							<div
								v-else-if="!sources.length"
								class="rounded-md border border-dashed border-outline-gray-2 px-3 py-6 text-center text-sm text-ink-gray-5"
							>
								{{ __("No sources yet.") }}
							</div>

							<button
								v-for="s in sources"
								:key="s.name"
								class="flex items-center gap-3 rounded-md border border-outline-gray-1 px-3 py-2 text-left hover:border-outline-gray-3 hover:bg-surface-gray-1"
								@click="openSource(s.name)"
							>
								<div class="min-w-0 flex-1">
									<div class="truncate text-sm font-normal text-ink-gray-9">{{ s.title }}</div>
									<div class="truncate text-xs text-ink-gray-5">{{ s.source_type }}</div>
								</div>
								<span class="shrink-0 text-xs text-ink-gray-5">
									{{ __("{0} chunks", [s.chunk_count || 0]) }}
								</span>
								<span
									class="shrink-0 rounded-full px-2 py-0.5 text-xs"
									:class="statusTheme(s.status)"
									>{{ s.status }}</span
								>
							</button>

							<button
								class="flex items-center justify-center gap-1.5 rounded-md border border-dashed border-outline-gray-2 py-2 text-xs text-ink-gray-6 hover:bg-surface-gray-2"
								@click="newSource"
							>
								<FeatherIcon name="plus" class="h-3.5 w-3.5" />
								{{ __("Add Source") }}
							</button>
						</div>
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
