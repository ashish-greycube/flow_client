// Dark mode for the Flow panel — independent of, but defaulting to, the
// desk's own light/dark setting. Shared by both bundles (the full chat page
// and the floating widget): each mounts its own #flow-root, and theme.css
// scopes every dark-mode override to `#flow-root[data-theme="dark"]`, so
// flipping this never touches the desk's own chrome outside the panel.
const THEME_KEY = "flow-theme"; // "light" | "dark" in storage; absent = follow the desk

function desktopTheme() {
	return document.documentElement.getAttribute("data-theme") || "light";
}

// Called on every read/write rather than cached: the widget and the full
// chat page each own a *different* #flow-root element, and either one may
// remount into a fresh DOM node (e.g. the widget's own show/hide cycle).
function flowRoot() {
	return document.getElementById("flow-root");
}

export function getThemeOverride() {
	try {
		return localStorage.getItem(THEME_KEY);
	} catch {
		return null;
	}
}

// The theme actually in effect: the user's explicit choice here if they've
// made one, otherwise whatever the desk itself is set to.
export function currentTheme() {
	return getThemeOverride() || desktopTheme();
}

export function applyTheme() {
	const root = flowRoot();
	if (root) root.setAttribute("data-theme", currentTheme());
}

export function setThemeOverride(theme) {
	try {
		localStorage.setItem(THEME_KEY, theme);
	} catch {
		// The preference is optional when browser storage is unavailable.
	}
	applyTheme();
}

export function toggleTheme() {
	setThemeOverride(currentTheme() === "dark" ? "light" : "dark");
}

// Keeps the panel in sync with the desk's own theme changes, but only for as
// long as the user hasn't set an explicit override of their own here.
export function watchDesktopTheme() {
	new MutationObserver(() => {
		if (!getThemeOverride()) applyTheme();
	}).observe(document.documentElement, {
		attributes: true,
		attributeFilter: ["data-theme"],
	});
}
