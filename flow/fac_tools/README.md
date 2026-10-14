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

## Report execution

`generate_report` handles heavy reports the way Jarvis's `run_report` does:

- A report flagged **Prepared Report** runs in Frappe's background job (`long` queue). The tool returns a `status`: `ready` (a completed run for the same user and filters, reused with its `as_of` time), `generating`, `started`, or `failed`. Asking again with the same filters returns the stored run without running the report again. Filters are matched on meaning, so runs started from Desk are reused too.
- Other reports run inline, and each query may run for at most `INLINE_QUERY_TIMEOUT` seconds. A report that takes longer is flagged as prepared (unless its "Disable Prepared Report Automation" setting is checked), and a background run starts.
- Flow runs the whole agent turn inside one job, which keeps a worker busy. A background run is only started when an **idle** worker listens on the `long` queue. Otherwise the report runs inline, because a queued run would not start until the turn ended.
- A started or in-flight run is waited on for up to `WAIT_SECONDS` (45s). This happens once per turn for the same report and filters. A later call in the same turn returns immediately, and its message tells the model to stop polling and tell the user.
- A failed run returns the reason from its traceback (for example "From Date and To Date are mandatory"), so the model can fix the filters.
- Filter discovery also reads filters that a report copies from a shared builder (ERPNext's `financial_statements.js`, used by P&L, Balance Sheet, Cash Flow and others) and filters it adds with `filters.push(...)`. A `mandatory_depends_on` condition is returned as `required_when`, and `apply_defaults` enforces simple `doc.field == 'value'` conditions.
- `column_totals` sums the Currency, Float, and Int columns over all rows. It is omitted for tree reports, and Currency columns are skipped when rows mix currencies.

The agent loop also caps every tool result at about 35K characters (`flow.lib.result_budget`). An oversized row list is cut, and a note says the result is partial.

Flow already provides equivalent document, metadata, workflow-action, knowledge-search, and sandbox tools. This package does not duplicate those tools.

Write tools use Flow's confirmation gate. All data tools check Frappe permissions before they return or change data.

The adapted logic comes from Frappe Assistant Core. Both projects use the AGPL-3.0-or-later license.

## Prebuilt agents

`prebuilt_agents.json` contains a self-contained, description-based adaptation of the Jarvis agent catalog. Migration creates every catalog entry as a protected, system-generated Flow Agent after an enabled Flow Model exists. The same sync runs when the first enabled model is created.

Each agent receives only the existing Flow and FAC tools needed for its role. Its instructions define a strict DocType allowlist, while the reused tools apply normal Frappe role, field, row, company, and User Permission checks. Auditor agents receive read/report/analysis/export tools only. Operator agents additionally receive Flow's confirmed create and update tools, constrained by their declared write contract in the instructions. Agents with missing required apps or DocTypes, and catalog entries marked Coming Soon, are created disabled.

Operator agents use the native `Flow Approval Request` DocType when they need a human decision. Requests are owner-scoped, decision fields are restricted to System Managers, and completed decisions can leave a permission-checked audit comment on the referenced business document.
