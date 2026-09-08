import frappe

ROLE_NAME = "Flow User"


def after_install():
    """Create the flow user role on a fresh install."""
    if frappe.db.exists("Role", ROLE_NAME):
        return
    role = frappe.new_doc("Role")
    role.role_name = ROLE_NAME
    role.desk_access = 1
    role.insert(ignore_permissions=True)
    frappe.db.commit()
