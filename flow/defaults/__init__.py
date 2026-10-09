"""Default records Flow creates on install and after every migrate.

Each feature lists its defaults as specs in its own module and registers them in DEFAULT_SPECS.
A spec looks like:

	{
		"doc": {"doctype": "...", ...field values, child tables as lists of dicts...},
		"match": ["fieldname", ...],          # fields that identify an existing record
		"required_apps": ["hrms"],            # optional: skip unless these apps are installed
		"requires": [("Flow Agent", "Flow")], # optional: skip until these records exist
	}

A default is created only when no record matches, so existing records and user edits are
never overwritten. A deleted default is created again on the next migrate.
"""

import frappe

from flow.defaults.macros import DEFAULT_MACROS
from flow.defaults.providers import DEFAULT_PROVIDERS

DEFAULT_SPECS = [*DEFAULT_PROVIDERS, *DEFAULT_MACROS]


def create_defaults():
	installed_apps = set(frappe.get_installed_apps())
	for spec in DEFAULT_SPECS:
		if not _can_create(spec, installed_apps):
			continue
		# A default that fails validation must not abort the install or migrate it runs in.
		try:
			frappe.get_doc(spec["doc"]).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Flow default not created: {spec['doc']['doctype']}")


def _can_create(spec, installed_apps):
	if not set(spec.get("required_apps") or []) <= installed_apps:
		return False
	if not all(frappe.db.exists(doctype, name) for doctype, name in spec.get("requires") or []):
		return False
	doc = spec["doc"]
	filters = {fieldname: doc[fieldname] for fieldname in spec["match"]}
	return not frappe.db.exists(doc["doctype"], filters)
