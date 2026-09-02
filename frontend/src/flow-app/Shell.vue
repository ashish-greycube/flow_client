<script setup>
import { RouterView } from "vue-router";
import Sidebar from "./Sidebar.vue";
</script>

<template>
	<div class="flow-panel flow-app flex h-full min-h-0 overflow-hidden text-ink-gray-9">
		<Sidebar />
		<RouterView />
	</div>
</template>
