import { createApp, watch } from "vue";
import App from "@/App.vue";
import { useStore } from "@/store";
import { writePanelState } from "@/lib/panelState";
import { applyTheme, watchDesktopTheme } from "@/lib/theme";
import "@/index.css";

// Floating chat widget injected into every desk page: a launcher button that
// toggles a small popup (App.vue), with a "Full chat" link out to the
// full-page Flow Chat (flow/flow/page/flow_chat). Replaces the old full-height
// slide-in panel — Ctrl+I still toggles the popup as a shortcut.
class FlowWidget {
	constructor() {
		this._mount();
		this._syncTheme();
		this._registerShortcut();
		this._hideOnFullChatPage();

		watch(this.store.sessionName, () => this._persist());
	}

	_mount() {
		this.store = useStore();

		this.root = document.createElement("div");
		this.root.id = "flow-root";
		document.body.appendChild(this.root);

		this.app = createApp(App, { onOpenFullChat: () => this.openFullChat() });
		// The mounted instance exposes show/hide/toggle (via defineExpose) — the
		// bridge between this plain controller class and the component's own
		// reactive `visible` state.
		this.vm = this.app.mount(this.root);
	}

	// Mirror the desk's light/dark theme onto the widget root, unless the user
	// has set their own light/dark preference from the full chat page's
	// sidebar (shared via localStorage — src/lib/theme.js).
	_syncTheme() {
		applyTheme();
		watchDesktopTheme();
	}

	_registerShortcut() {
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+i",
			action: () => this.vm.toggle(),
			description: __("Toggle Flow chat widget"),
			ignore_inputs: true,
		});
	}

	openFullChat() {
		this.vm.hide();
		frappe.set_route("flow-chat");
	}

	// Detach the widget entirely while the full-page Flow Chat is already open —
	// a floating "chat with Flow" bubble on top of that page would just be a
	// redundant second entry point to the same thing. This removes #flow-root
	// from the DOM outright rather than just hiding it: the chat page's own
	// bundle mounts its own #flow-root (same id, for the same shared CSS
	// scoping — see postcss.config.js), and every Combobox in this app
	// resolves its `portal-to="#flow-root"` target via a plain CSS-selector
	// lookup, which would otherwise resolve to whichever of the two elements
	// happens to come first in the DOM instead of the caller's own container.
	//
	// The very first check runs off `window.location.pathname`, not
	// `frappe.get_route()`: the route is still null when app_ready fires
	// (routing resolves asynchronously, after app_ready), so checking the
	// route object here would let the launcher render for one paint before
	// the later "change" event corrects it — a visible flash on every load of
	// the chat page. The URL itself is already correct at this point.
	_hideOnFullChatPage() {
		const isFullChatPath = () => window.location.pathname.split("/").includes("flow-chat");
		const sync = (usePathname) => {
			const onFullChat = usePathname ? isFullChatPath() : (frappe.get_route() || [])[0] === "flow-chat";
			if (onFullChat) {
				this.vm.hide();
				this.root.remove();
			} else if (!this.root.isConnected) {
				document.body.appendChild(this.root);
			}
		};
		sync(true);
		frappe.router.on("change", () => sync(false));
	}

	_persist() {
		writePanelState({ session: this.store.sessionName.value });
	}
}

frappe.provide("frappe.flow");
$(document).on("app_ready", () => {
	frappe.flow.widget = new FlowWidget();
});
