<script setup>
// Trusted first-party File URL (a Flow File2ERP entry's own attachment) — a plain
// <iframe>/<img> is enough, no viewer library needed.
import { computed } from "vue";
import { FeatherIcon } from "@/lib/ui";
import { __ } from "@/lib/translate";

const props = defineProps({
	fileUrl: { type: String, default: "" },
	fileName: { type: String, default: "" },
});

const IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif"];

const extension = computed(() => (props.fileName.split(".").pop() || "").toLowerCase());
const kind = computed(() => {
	if (extension.value === "pdf") return "pdf";
	if (IMAGE_EXTENSIONS.includes(extension.value)) return "image";
	return "other";
});
</script>

<template>
	<div class="flex h-full min-h-0 flex-col items-center justify-center overflow-hidden bg-surface-gray-1">
		<iframe v-if="kind === 'pdf' && fileUrl" :src="fileUrl" class="h-full w-full border-0" :title="fileName" />
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
