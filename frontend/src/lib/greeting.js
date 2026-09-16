import { __ } from "./translate";

// Time-of-day greeting for the empty chat state ("Good morning, Jane").
// Plain and deterministic on purpose — this is a desk tool, not a fun surprise.
export function timeGreeting(date = new Date()) {
	const hour = date.getHours();
	if (hour < 12) return __("Good morning");
	if (hour < 17) return __("Good afternoon");
	return __("Good evening");
}

// The desk's own fullname lookup ("frappe.user.full_name") returns "You" for
// the current session user, which reads oddly in a greeting — go straight to
// user_info instead, with the same "Unknown" fallback it uses internally.
export function currentUserName() {
	if (typeof frappe === "undefined") return "";
	return frappe.user_info(frappe.session.user).fullname;
}

// Profile image + display name for the logged-in user, for the chat avatar.
// Colour/initial come straight from frappe.get_palette/get_abbr — the same
// pair the desk navbar and comment threads use for a user's initials avatar
// (a deterministic colour per name, not random), so the chat matches it
// rather than inventing its own scheme.
export function currentUserInfo() {
	if (typeof frappe === "undefined") return { image: "", fullname: "", abbr: "?", palette: null };
	const info = frappe.user_info(frappe.session.user);
	const fullname = info.fullname || "";
	return {
		image: info.image || "",
		fullname,
		abbr: frappe.get_abbr(fullname).substr(0, 1),
		palette: frappe.get_palette(fullname), // [bgVar, colorVar]
	};
}
