import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// Builds the consolidated Flow app (frontend/src/flow-app) as a single
// self-contained IIFE bundle + one CSS file — Sidebar + vue-router shell with
// Chat/Agents/Flow Guide as routed views underneath. Replaces the earlier
// vite.chat.config.js + vite.agents.config.js pair (Agents was a wholly
// separate Frappe Page + bundle with no sidebar of its own). Emitted into
// the same flow_chat output dir/filenames as before so the existing
// "flow-chat" desk page (flow/flow/page/flow_chat) needs no changes — it just
// loads a bigger bundle now. Separate from the slide-in widget bundle built
// by vite.config.js; the two never load on the same page.
export default defineConfig({
	define: {
		"process.env.NODE_ENV": JSON.stringify("production"),
		__VUE_OPTIONS_API__: "true",
		__VUE_PROD_DEVTOOLS__: "false",
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "false",
	},
	plugins: [vue()],
	resolve: {
		alias: [
			{ find: "@", replacement: fileURLToPath(new URL("./frontend/src", import.meta.url)) },
			{
				find: "frappe-ui/src",
				replacement: fileURLToPath(
					new URL("./node_modules/frappe-ui/src", import.meta.url)
				),
			},
		],
	},
	build: {
		outDir: fileURLToPath(new URL("./flow/public/flow_chat", import.meta.url)),
		emptyOutDir: true,
		cssCodeSplit: false,
		sourcemap: false,
		target: "es2017",
		lib: {
			entry: fileURLToPath(new URL("./frontend/src/flow-app/main.js", import.meta.url)),
			formats: ["iife"],
			name: "FlowApp",
			fileName: () => "flow_chat.js",
		},
		rollupOptions: {
			output: { assetFileNames: "flow_chat.[ext]" },
		},
	},
});
