// Single import point for the frappe-ui components used by the panel. They are
// pulled from source (aliased in vite.config.js) and tree-shaken into the bundle.
export { default as Button } from "frappe-ui/src/components/Button/Button.vue";
export { default as FeatherIcon } from "frappe-ui/src/components/FeatherIcon.vue";
export { default as Spinner } from "frappe-ui/src/components/Spinner.vue";
export { default as Badge } from "frappe-ui/src/components/Badge/Badge.vue";
// Every component here is imported straight from its own source file rather
// than through frappe-ui's `FormControl` dispatcher: FormControl eagerly
// imports every field-type branch it supports (including icon-heavy ones like
// Rating), which drags in unplugin-icons virtual imports this bundle would
// otherwise need a whole extra Vite plugin for. Importing a component
// directly, as below, only pulls in what that component itself needs —
// verified none of these have an unplugin-icons dependency of their own.
export { default as TextInput } from "frappe-ui/src/components/TextInput/TextInput.vue";
export { default as Textarea } from "frappe-ui/src/components/Textarea/Textarea.vue";
export { default as Switch } from "frappe-ui/src/components/Switch/Switch.vue";
export { default as Breadcrumbs } from "frappe-ui/src/components/Breadcrumbs/Breadcrumbs.vue";
// Combobox teleports its popover content out of the DOM tree it's mounted in.
// It accepts `portalTo`, which every usage here must set to `"#flow-root"` —
// the panel's CSS is scoped to that id at build time (postcss-prefix-selector),
// so content teleported to `document.body` (the default) would render
// completely unstyled.
export { default as Combobox } from "frappe-ui/src/components/Combobox/Combobox.vue";
