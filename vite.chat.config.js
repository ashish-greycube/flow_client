import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// Builds the full-page Flow Chat UI (frontend/src/chat-page) as a single
// self-contained IIFE bundle + one CSS file, emitted into the app's public
// dir. Loaded on demand by the "flow-chat" desk page (see
// flow/flow/page/flow_chat) via frappe.require — separate from the slide-in
// panel bundle built by vite.config.js, which the two never load together.
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
			entry: fileURLToPath(new URL("./frontend/src/chat-page/main.js", import.meta.url)),
			formats: ["iife"],
			name: "FlowChatPage",
			fileName: () => "flow_chat.js",
		},
		rollupOptions: {
			output: { assetFileNames: "flow_chat.[ext]" },
		},
	},
});
