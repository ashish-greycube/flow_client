# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Single gate for "does this user get to use Flow at all". DocType permissions
and page/workspace roles keep out unauthorized access to Desk views and list
data, but several whitelisted endpoints deliberately insert with
ignore_permissions=True and rely on their own ownership checks (see
flow.lib.session) rather than doctype create permissions — so those endpoints
must call require_flow_user() themselves to enforce the role."""

from __future__ import annotations

import frappe
from frappe import _

ROLE = "Flow User"


def is_flow_user(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return ROLE in roles or "System Manager" in roles


def require_flow_user() -> None:
	if not is_flow_user():
		frappe.throw(
			_('You need the "{0}" role to access Flow.').format(ROLE),
			frappe.PermissionError,
			title=_("Not Permitted"),
		)
