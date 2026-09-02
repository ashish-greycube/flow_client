// Single import point for the frappe-ui components used by the panel. They are
// pulled from source (aliased in vite.config.js) and tree-shaken into the bundle.
export { default as Button } from "frappe-ui/src/components/Button/Button.vue";
export { default as FeatherIcon } from "frappe-ui/src/components/FeatherIcon.vue";
export { default as Spinner } from "frappe-ui/src/components/Spinner.vue";
export { default as Badge } from "frappe-ui/src/components/Badge/Badge.vue";
// TextInput/Textarea directly, not the FormControl dispatcher: FormControl's
// other branches (Combobox/Autocomplete/DatePicker/...) pull in unplugin-icons
// virtual imports this bundle would otherwise need a whole extra Vite plugin
// for, just to support two field types we don't use.
export { default as TextInput } from "frappe-ui/src/components/TextInput/TextInput.vue";
export { default as Textarea } from "frappe-ui/src/components/Textarea/Textarea.vue";
export { default as Switch } from "frappe-ui/src/components/Switch/Switch.vue";
export { default as Breadcrumbs } from "frappe-ui/src/components/Breadcrumbs/Breadcrumbs.vue";
