import frappe

ROLE_NAME = "Flow User"


def after_install():
    """Create the Flow User role and Flow's tools on a fresh install. Also runs after
    every migrate. The built-in agents follow once a Flow Model exists."""
    if not frappe.db.exists("Role", ROLE_NAME):
        role = frappe.new_doc("Role")
        role.role_name = ROLE_NAME
        role.desk_access = 1
        role.insert(ignore_permissions=True)
    _sync_tools()
    frappe.db.commit()


def _sync_tools():
    from flow.fac_tools.registry import FAC_TOOLS, _sync_tool
    from flow.tools.builtins import sync_builtin_tools
    from flow.tools.file2erp import sync_file2erp_tool
    from flow.tools.ocr import sync_ocr_tool

    sync_builtin_tools()
    sync_ocr_tool()
    sync_file2erp_tool()
    for advanced_tool in FAC_TOOLS:
        _sync_tool(advanced_tool)
