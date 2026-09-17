<script setup>
import { computed } from "vue";
import AttachmentChip from "./AttachmentChip.vue";
import { currentUserInfo } from "@/lib/greeting";

defineProps({
	content: { type: String, default: "" },
	attachments: { type: Array, default: () => [] },
});

const user = currentUserInfo();

const avatarStyle = computed(() =>
	user.palette
		? {
				backgroundColor: `var(${user.palette[0]})`,
				color: `var(${user.palette[1]})`,
			}
		: { backgroundColor: "#14110f", color: "#e8e3da" }
);
</script>

<template>
	<div class="flex w-full min-w-0 items-start justify-end gap-2.5">
		<div class="flex min-w-0 max-w-[85%] flex-col items-end gap-1.5">
			<div
				v-if="attachments.length"
				class="flex max-w-full flex-wrap justify-end gap-1.5"
			>
				<AttachmentChip
					v-for="(a, i) in attachments"
					:key="`${a.file_name}-${i}`"
					:file-name="a.file_name"
					:file-size="a.file_size"
				/>
			</div>

			<div
				class="w-fit max-w-full whitespace-pre-wrap break-words rounded-2xl bg-surface-gray-4 px-3.5 py-2.5 text-[length:var(--text-base)] font-normal leading-relaxed text-ink-gray-9"
			>
				{{ content }}
			</div>
		</div>

		<div
			class="mt-1 flex h-[36px] w-[36px] shrink-0 items-center justify-center overflow-hidden rounded-[10px] border border-outline-gray-2 text-[14px] font-medium uppercase"
			:style="user.image ? null : avatarStyle"
		>
			<img
				v-if="user.image"
				:src="user.image"
				:alt="user.fullname"
				class="h-full w-full object-cover"
			/>
			<span v-else>{{ user.abbr }}</span>
		</div>
	</div>
</template>