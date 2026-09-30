# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""User-authored conditions, run in the server-script sandbox (safe_exec).

A condition is either a single Python expression whose value is the verdict,
or a multi-line script that sets a `result` variable. Authoring is restricted
to System Managers (Flow Trigger / Flow Knowledge Source permissions), the
same trust level frappe requires for Server Scripts.

Server Scripts are off by default, and safe_exec refuses to run without them.
A single expression then falls back to frappe.safe_eval — the evaluator frappe
itself uses for Workflow and Notification conditions — so the common case keeps
working. A multi-line script has no such fallback and is rejected on save.
"""

from __future__ import annotations

import ast
from typing import Any

import frappe
from frappe import _
from frappe.utils.safe_exec import get_safe_globals, is_safe_exec_enabled, safe_exec

RESULT_VAR = "result"

_EXPRESSION_BUILTINS = {
	"len": len,
	"str": str,
	"bool": bool,
	"abs": abs,
	"min": min,
	"max": max,
	"sum": sum,
	"any": any,
	"all": all,
}


def validate_condition(condition: str | None) -> None:
	"""Save-time check: a single expression, or a script that sets `result`."""
	if not condition:
		return
	if _is_expression(condition):
		return
	try:
		tree = ast.parse(condition)
	except SyntaxError as e:
		frappe.throw(_("Invalid condition: {0}").format(e), title=_("Invalid Condition"))
	if not _assigns_result(tree):
		frappe.throw(
			_("A multi-line condition must set a <code>result</code> variable."),
			title=_("Invalid Condition"),
		)
	if not is_safe_exec_enabled():
		frappe.throw(
			_(
				"Multi-line conditions need Server Scripts to be enabled. Use a single expression instead."
			),
			title=_("Invalid Condition"),
		)


def evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
	"""Run `condition` in the sandbox with `context` in scope; return the verdict.
	Raises on execution errors — callers decide how to fail."""
	if _is_expression(condition):
		if not is_safe_exec_enabled():
			return bool(frappe.safe_eval(condition, None, {**_expression_namespace(), **context}))
		condition = f"{RESULT_VAR} = ({condition}\n)"
	exec_globals, _locals = safe_exec(condition, context, script_filename="flow_condition")
	return bool(exec_globals.get(RESULT_VAR))


def _expression_namespace() -> dict[str, Any]:
	"""Names an expression can use without Server Scripts: read-only lookups, the
	current user and the safe utils, mirroring frappe's workflow conditions."""
	return {
		**_EXPRESSION_BUILTINS,
		"frappe": frappe._dict(
			db=frappe._dict(get_value=frappe.db.get_value, get_list=frappe.db.get_list),
			session=frappe._dict(user=frappe.session.user),
			utils=get_safe_globals().get("frappe").get("utils"),
		),
	}


def _is_expression(condition: str) -> bool:
	try:
		compile(condition, "<flow_condition>", "eval")
		return True
	except SyntaxError:
		return False


# Scopes that don't execute in the module body, so a `result` assigned inside them
# never reaches the exec globals the verdict is read from.
_NESTED_SCOPES = (
	ast.FunctionDef,
	ast.AsyncFunctionDef,
	ast.ClassDef,
	ast.Lambda,
	ast.ListComp,
	ast.SetComp,
	ast.DictComp,
	ast.GeneratorExp,
)


def _assigns_result(node: ast.AST) -> bool:
	"""Whether `result` is assigned in the module's own scope. Recurses through control
	flow (if/for/try) but not into nested scopes, which never run in the exec globals."""
	for child in ast.iter_child_nodes(node):
		if isinstance(child, _NESTED_SCOPES):
			continue
		if _targets_result(child) or _assigns_result(child):
			return True
	return False


def _targets_result(node: ast.AST) -> bool:
	if isinstance(node, ast.Assign):
		targets = node.targets
	elif isinstance(node, ast.AugAssign | ast.AnnAssign | ast.NamedExpr):
		targets = [node.target]
	else:
		return False
	return any(_is_result_name(target) for target in targets)


def _is_result_name(target: ast.AST) -> bool:
	if isinstance(target, ast.Name):
		return target.id == RESULT_VAR
	if isinstance(target, ast.Tuple | ast.List):
		return any(_is_result_name(el) for el in target.elts)
	return False
