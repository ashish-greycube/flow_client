<script setup>
import { computed } from "vue";
import AttachmentChip from "./AttachmentChip.vue";
import { currentUserInfo } from "@/lib/greeting";

defineProps({
	content: { type: String, default: "" },
	attachments: { type: Array, default: () => [] },
});

const user = currentUserInfo();
// Same colour pair the desk navbar/comments use for this user's initial
// (frappe.get_palette), falling back to the brand-dark square if frappe's
// palette isn't available (e.g. outside the desk).
const avatarStyle = computed(() =>
	user.palette
		? { backgroundColor: `var(${user.palette[0]})`, color: `var(${user.palette[1]})` }
		: { backgroundColor: "#14110f", color: "#e8e3da" }
);
</script>

<template>
	<div class="flex items-start justify-end gap-2.5">
		<div class="flex min-w-0 flex-col items-end gap-1.5">
			<div v-if="attachments.length" class="flex max-w-[88%] flex-wrap justify-end gap-1.5">
				<AttachmentChip
					v-for="(a, i) in attachments"
					:key="`${a.file_name}-${i}`"
					:file-name="a.file_name"
					:file-size="a.file_size"
				/>
			</div>
			<div
				class="max-w-[88%] whitespace-pre-wrap break-words rounded-2xl bg-surface-gray-4 px-3.5 py-2.5 text-[length:var(--text-base)] font-normal leading-relaxed text-ink-gray-9"
			>
				{{ content }}
			</div>
		</div>
		<!-- Matches the desk navbar/comment-thread avatar: a circle, a photo when
		set, otherwise the user's initial on their frappe.get_palette colour —
		not frappe-ui's Avatar component, whose no-image fallback hardcodes a
		flat light-grey-on-grey with no way to plug that palette in. -->
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
