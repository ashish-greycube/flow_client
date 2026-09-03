# vendor/

Third-party browser bundles loaded at runtime via a plain `<script>` tag
(`frontend/src/lib/loadEcharts.js`), not through Vite — kept out of the app's
own JS bundles since echarts alone is ~350KB gzipped and isn't meaningfully
tree-shakeable through its package entry point, and this app's bundles build
as self-contained IIFE files that can't code-split a dynamic import away from
the main bundle either. Only fetched the first time a chat message actually
renders a chart (`create_chart` tool, `ChartCard.vue`).

- `echarts.min.js` — Apache ECharts 5.6.0 UMD build (`node_modules/echarts/dist/echarts.min.js`), Apache-2.0 (`echarts.LICENSE`). Bump the version here by re-copying that file when `frappe-ui`'s own echarts dependency version changes.
