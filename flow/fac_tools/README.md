# FAC tools for Flow

This package adds Frappe Assistant Core capabilities that upstream Flow does not provide.

The package does not change `flow.tools.builtins`. The `after_migrate` hook calls `sync_fac_tools` after Flow syncs its built-in tools.

## Added tools

- Search: `search_documents`, `search_doctype`, and `search_link`
- Reports: `report_list`, `report_requirements`, and `generate_report`
- Export: `export_excel`
- Workflow: `get_pending_approvals`
- Analysis: `run_python_code`, `analyze_business_data`, and `run_database_query`
- Files: `extract_file_content`
- Dashboards: `create_dashboard`, `create_dashboard_chart`, and `list_user_dashboards`

Flow already provides equivalent document, metadata, workflow-action, knowledge-search, and sandbox tools. This package does not duplicate those tools.

Write tools use Flow's confirmation gate. All data tools check Frappe permissions before they return or change data.

The adapted logic comes from Frappe Assistant Core. Both projects use the AGPL-3.0-or-later license.
