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
