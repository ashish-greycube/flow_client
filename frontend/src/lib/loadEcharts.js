// Loads echarts from a plain <script> tag at runtime instead of bundling it
// through Vite. echarts isn't meaningfully tree-shakeable via its package
// entry point (~350KB gzipped regardless of which chart types are actually
// used), and this app's bundles build as self-contained IIFE files (loaded
// via frappe.require()) that can't code-split a dynamic import() away from
// the main bundle either — a static OR dynamic `import "echarts"` both land
// in the one shipped file either way. Charts are rare enough in a
// conversation that paying this cost only when one actually renders — as a
// separately-fetched script, not bundled JS — is worth the extra runtime
// loading code. See flow/public/vendor/README.md for the vendored file itself.
let promise = null;

export function loadEcharts() {
	if (window.echarts) return Promise.resolve(window.echarts);
	if (promise) return promise;
	promise = new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.src = "/assets/flow/vendor/echarts.min.js";
		script.onload = () => resolve(window.echarts);
		script.onerror = () => {
			promise = null; // let the next chart attempt retry instead of failing forever
			reject(new Error("Could not load the charting library."));
		};
		document.head.appendChild(script);
	});
	return promise;
}
