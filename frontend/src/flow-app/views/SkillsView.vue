<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import SearchInput from "@/components/SearchInput.vue";
import { Button, FeatherIcon, Spinner, Badge } from "@/lib/ui";
import { __ } from "@/lib/translate";
import { loadAllSkills } from "@/api/client";

const router = useRouter();
const loading = ref(true);
const skills = ref([]);
const query = ref("");

const canCreate = computed(() => (frappe.boot.user?.can_create || []).includes("Flow Skill"));
const filtered = computed(() => {
	const value = query.value.trim().toLowerCase();
	if (!value) return skills.value;
	return skills.value.filter((skill) =>
		[skill.title, skill.command, skill.description].some((field) =>
			(field || "").toLowerCase().includes(value),
		),
	);
});

onMounted(async () => {
	try {
		skills.value = await loadAllSkills();
	} finally {
		loading.value = false;
	}
});

function openSkill(name) {
	router.push({ name: "skill-edit", params: { name } });
}

function newSkill() {
	router.push({ name: "skill-new" });
}
</script>

<template>
	<div
		class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-white text-ink-gray-9"
	>
		<header class="flex items-center justify-between border-b border-outline-gray-1 px-6 py-4">
			<h1 class="text-lg font-normal text-ink-gray-9">{{ __("Skills") }}</h1>
			<Button v-if="canCreate" variant="solid" @click="newSkill">
				<template #prefix><FeatherIcon name="plus" class="h-3.5 w-3.5" /></template>
				{{ __("New Skill") }}
			</Button>
		</header>

		<div class="px-6 py-4">
			<SearchInput
				v-model="query"
				:placeholder="__('Search skills or commands…')"
				class="max-w-sm rounded-lg border border-outline-gray-2"
			/>
		</div>

		<div class="flow-scrollbar flex-1 overflow-y-auto px-6 pb-8">
			<div v-if="loading" class="flex justify-center py-16">
				<Spinner class="h-5 w-5 text-ink-gray-5" />
			</div>
			<div v-else-if="!filtered.length" class="py-16 text-center text-sm text-ink-gray-5">
				{{ query.trim() ? __("No matching skills.") : __("No skills yet.") }}
			</div>
			<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
				<button
					v-for="skill in filtered"
					:key="skill.name"
					class="flex flex-col gap-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4 text-left hover:border-outline-gray-3 hover:shadow-sm"
					@click="openSkill(skill.name)"
				>
					<div class="flex min-w-0 items-start justify-between gap-3">
						<div class="min-w-0">
							<div class="truncate text-sm font-semibold text-ink-gray-9">
								{{ skill.title }}
							</div>
							<div class="truncate font-mono text-xs text-ink-gray-5">
								/{{ skill.command }}
							</div>
						</div>
						<FeatherIcon name="zap" class="h-4 w-4 shrink-0 text-ink-gray-5" />
					</div>
					<p class="line-clamp-2 text-sm leading-relaxed text-ink-gray-6">
						{{ skill.description || __("No description set.") }}
					</p>
					<div class="mt-auto flex items-center gap-1.5">
						<Badge
							variant="subtle"
							:theme="skill.enabled ? 'green' : 'gray'"
							:label="skill.enabled ? __('Enabled') : __('Disabled')"
						/>
						<Badge
							v-if="skill.is_system_generated"
							variant="subtle"
							theme="gray"
							:label="__('Built in')"
						/>
					</div>
				</button>
			</div>
		</div>
	</div>
</template>
