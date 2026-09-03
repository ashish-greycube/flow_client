<script setup>
import { RouterView } from "vue-router";
import Sidebar from "./Sidebar.vue";
import Navbar from "./Navbar.vue";
</script>

<template>
	<div class="flow-panel flow-app flex h-full min-h-0 overflow-hidden text-ink-gray-9">
		<Sidebar />
		<div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
			<Navbar />
			<RouterView />
		</div>
	</div>
</template>
