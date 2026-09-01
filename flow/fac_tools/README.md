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

## Prebuilt agents

`prebuilt_agents.json` contains a self-contained, description-based adaptation of the Jarvis agent catalog. Migration creates every catalog entry as a protected, system-generated Flow Agent after an enabled Flow Model exists. The same sync runs when the first enabled model is created.

Each agent receives only the existing Flow and FAC tools needed for its role. Its instructions define a strict DocType allowlist, while the reused tools apply normal Frappe role, field, row, company, and User Permission checks. Auditor agents receive read/report/analysis/export tools only. Operator agents additionally receive Flow's confirmed create and update tools, constrained by their declared write contract in the instructions. Agents with missing required apps or DocTypes, and catalog entries marked Coming Soon, are created disabled.

Operator agents use the native `Flow Approval Request` DocType when they need a human decision. Requests are owner-scoped, decision fields are restricted to System Managers, and completed decisions can leave a permission-checked audit comment on the referenced business document.
