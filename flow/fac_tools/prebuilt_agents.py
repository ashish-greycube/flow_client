# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe

SOURCE_LABEL = "Jarvis description-based Flow adaptation"
READ_TOOLS = (
	"describe",
	"read",
	"search_doctype",
	"report_list",
	"report_requirements",
	"generate_report",
	"export_excel",
	"analyze_business_data",
)
WRITE_TOOLS = ("create", "update")


def load_prebuilt_catalog() -> list[dict[str, Any]]:
	with Path(__file__).with_name("prebuilt_agents.json").open(encoding="utf-8") as source:
		return json.load(source)["agents"]


def sync_prebuilt_agents(model: str | None = None) -> None:
	"""Create or refresh protected prebuilt agents when an enabled Flow Model exists."""
	model_name = model or frappe.db.get_value("Flow Model", {"enabled": 1}, "name")
	if not model_name:
		return
	for specification in load_prebuilt_catalog():
		_sync_agent(specification, model_name)


def sync_after_model_insert(doc, _method=None) -> None:
	if doc.enabled:
		sync_prebuilt_agents(model=doc.name)


def _sync_agent(specification: dict[str, Any], model_name: str) -> None:
	title = specification["title"]
	compatible = _is_compatible(specification)
	values = {
		"instructions": _instructions(specification),
		"max_iterations": 25 if specification["nature"].lower() == "operator" else 20,
		"tools": [{"tool": name} for name in _tool_names(specification)],
		"enabled": int(specification["status"] == "Published" and compatible),
		"is_system_generated": 1,
	}
	if not frappe.db.exists("Flow Agent", title):
		frappe.get_doc(
			{"doctype": "Flow Agent", "title": title, "model": model_name, **values}
		).insert(ignore_permissions=True)
		return
	doc = frappe.get_doc("Flow Agent", title)
	if not doc.is_system_generated:
		return
	doc.instructions = values["instructions"]
	doc.max_iterations = values["max_iterations"]
	doc.enabled = values["enabled"]
	doc.set("tools", values["tools"])
	doc.save(ignore_permissions=True)


def _is_compatible(specification: dict[str, Any]) -> bool:
	installed_apps = set(frappe.get_installed_apps())
	if any(app not in installed_apps for app in (specification.get("min_apps") or [])):
		return False
	return all(frappe.db.exists("DocType", doctype) for doctype in specification["doctypes_required"])


def _tool_names(specification: dict[str, Any]) -> tuple[str, ...]:
	return (*READ_TOOLS, *WRITE_TOOLS) if specification.get("writes") else READ_TOOLS


def _instructions(specification: dict[str, Any]) -> str:
	doctypes = "\n".join(f"- {doctype}" for doctype in specification["doctypes_required"])
	writes = specification.get("writes") or []
	write_section = _write_instructions(writes)
	return f"""You are the {specification['title']}, a prebuilt {specification['nature']} agent.

PURPOSE
{specification['description']}

HARD DATA SCOPE
You may inspect and read only these DocTypes:
{doctypes}

This allowlist is a mandatory operating boundary. The tools enforce the current user's Frappe permissions; you must additionally keep every tool call inside the DocTypes listed above. Never access another DocType, use guessed fields, request raw SQL, or ask for a broader tool. If required data is outside this scope or a DocType is unavailable, explain the limitation instead of working around it.

WORK METHOD
1. Translate the request into the smallest relevant subset of the allowed DocTypes.
2. Inspect a DocType before using unfamiliar fields.
3. Read with narrow filters, explicit fields, and small limits. Query child DocTypes directly when line-level evidence is required.
4. Use a saved report only when its reference DocType is in scope. Inspect its requirements before the first run.
5. Cross-check material findings against the underlying records. Separate facts, assumptions, missing evidence, and recommendations.
6. Report concise evidence first. Never describe incomplete coverage as a clean result.
{write_section}

PERMISSIONS AND SAFETY
All reads, reports, and writes run as the current Frappe user and must respect role, field, row, company, and User Permission restrictions. Never claim visibility beyond the returned data. Never submit, cancel, delete, email, file a statutory return, or perform an undeclared action.

SOURCE
This is a {SOURCE_LABEL} generated from catalog version {specification.get('version') or 'unknown'} for domain {specification['domain']}.
"""


def _write_instructions(writes: list[dict[str, Any]]) -> str:
	if not writes:
		return "\nREAD-ONLY RULE\nYou are strictly read-only. Produce findings and recommendations only. Never call create or update."
	contracts = "\n".join(f"- {row['doctype']}: {row['mode']}" for row in writes)
	return f"""
DECLARED WRITE CONTRACT
You may propose changes through Flow's confirmed create/update tools only for:
{contracts}
Before calling either tool, read the relevant evidence and show the exact proposed values. Create or update drafts only; never set docstatus. A successful draft is still a proposal requiring human review and submission."""
