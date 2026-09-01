import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// Builds the Flow Agents catalog page (frontend/src/agents-page) as a single
// self-contained IIFE bundle + one CSS file, emitted into the app's public
// dir. Loaded on demand by the "flow-agents" desk page (see
// flow/flow/page/flow_agents) via frappe.require — a separate bundle from
// both the chat page and the widget, never loaded alongside either.
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
		outDir: fileURLToPath(new URL("./flow/public/flow_agents", import.meta.url)),
		emptyOutDir: true,
		cssCodeSplit: false,
		sourcemap: false,
		target: "es2017",
		lib: {
			entry: fileURLToPath(new URL("./frontend/src/agents-page/main.js", import.meta.url)),
			formats: ["iife"],
			name: "FlowAgentsPage",
			fileName: () => "flow_agents.js",
		},
		rollupOptions: {
			output: { assetFileNames: "flow_agents.[ext]" },
		},
	},
});
