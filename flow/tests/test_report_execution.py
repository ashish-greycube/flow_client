# Copyright (c) 2026, Frappe Technologies and contributors
# License: AGPL-3.0-or-later

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import pymysql
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils.background_jobs import generate_qname

from flow.fac_tools import prepared_reports
from flow.fac_tools.report_filters import apply_defaults, discover_filters
from flow.fac_tools.reports import _run_inline, column_totals, generate_report, sort_rows
from flow.lib.agent import _serialize_tool_result
from flow.lib.result_budget import MAX_RESULT_CHARS, fit_result

ENQUEUE = "frappe.core.doctype.prepared_report.prepared_report.enqueue"
TRACEBACK = """Traceback with variables (most recent call last):
  File "apps/frappe/frappe/utils/messages.py", line 59, in _raise_exception
    raise exc
      msg = 'From Date and To Date are mandatory'
frappe.exceptions.ValidationError: From Date and To Date are mandatory
"""


class TestResultBudget(UnitTestCase):
	def test_small_result_is_unchanged(self):
		result = {"success": True, "data": [{"a": 1}]}
		self.assertIs(fit_result(result), result)

	def test_large_row_list_is_cut_to_fit_with_partial_note(self):
		rows = [{"name": f"ROW-{index}", "text": "x" * 200} for index in range(1000)]
		out = fit_result({"success": True, "data": rows, "note": "tool's own"})
		self.assertLessEqual(len(json.dumps(out, default=str)), MAX_RESULT_CHARS)
		self.assertTrue(out["_truncated"])
		self.assertEqual(out["total"], 1000)
		self.assertEqual(out["shown"], len(out["data"]))
		self.assertEqual(out["data"], rows[: out["shown"]])
		self.assertIn("PARTIAL", out["note"])
		self.assertTrue(out["success"])

	def test_analysis_groups_and_changes_are_cut_too(self):
		for key in ("groups", "changes"):
			out = fit_result({"success": True, key: [{"records": ["X" * 300]}] * 400})
			self.assertTrue(out["_truncated"], key)
			self.assertLessEqual(len(json.dumps(out, default=str)), MAX_RESULT_CHARS)

	def test_bare_list_is_wrapped(self):
		out = fit_result([{"text": "x" * 500}] * 200)
		self.assertTrue(out["_truncated"])
		self.assertIn("rows", out)

	def test_oversized_content_around_rows_drops_all_rows(self):
		out = fit_result({"query_executed": "x" * (MAX_RESULT_CHARS + 10), "data": [{"a": 1}]})
		self.assertEqual(out["data"], [])
		self.assertEqual(out["shown"], 0)

	def test_agent_serializes_through_the_cap(self):
		rows = [{"text": "x" * 500} for _ in range(500)]
		self.assertLessEqual(len(_serialize_tool_result({"data": rows})), MAX_RESULT_CHARS)


class TestColumnTotals(UnitTestCase):
	columns = [
		{"fieldname": "party", "fieldtype": "Link"},
		{"fieldname": "amount", "fieldtype": "Currency"},
		{"fieldname": "qty", "fieldtype": "Float"},
		{"fieldname": "margin", "fieldtype": "Percent"},
	]

	def test_sums_numeric_columns_and_skips_the_total_row(self):
		rows = [
			{"party": "A", "amount": 100, "qty": 1.5, "margin": 10},
			{"party": "B", "amount": 50.25, "qty": None, "margin": 20},
			["Total", 150.25, 1.5, 30],
		]
		self.assertEqual(column_totals(self.columns, rows), {"amount": 150.25, "qty": 1.5})

	def test_tree_report_has_no_totals(self):
		rows = [{"account": "Income", "amount": 10, "indent": 0}, {"account": "Sales", "amount": 10, "indent": 1}]
		self.assertIsNone(column_totals(self.columns, rows))

	def test_mixed_currencies_skip_money_totals(self):
		rows = [{"amount": 10, "qty": 1, "currency": "INR"}, {"amount": 5, "qty": 2, "currency": "USD"}]
		self.assertEqual(column_totals(self.columns, rows), {"qty": 3})


class TestPreparedReports(IntegrationTestCase):
	def setUp(self):
		self.report = frappe.db.get_value("Report", {"report_type": "Script Report", "disabled": 0}, "name")
		# Each test is a fresh turn, and does not wait for background runs unless it says so.
		frappe.flags.flow_report_waits = None
		wait = patch.object(prepared_reports, "WAIT_SECONDS", 0)
		wait.start()
		self.addCleanup(wait.stop)

	def make_run(self, filters, status):
		with patch(ENQUEUE):
			doc = frappe.get_doc(
				{"doctype": "Prepared Report", "report_name": self.report, "filters": json.dumps(filters)}
			).insert(ignore_permissions=True)
		doc.db_set("status", status)
		return doc.name

	def test_repeated_ask_reuses_the_completed_run(self):
		run = self.make_run({"show_zero": 1, "groups": ["b", "a"], "blank": ""}, "Completed")
		stored = json.dumps({"columns": [{"fieldname": "a"}], "result": [{"a": 1}]}).encode()
		with (
			patch.object(type(frappe.get_doc("Prepared Report", run)), "get_prepared_data", return_value=stored),
			patch("flow.fac_tools.prepared_reports.start") as start,
		):
			state = prepared_reports.handle(self.report, {"show_zero": True, "groups": ["a", "b"]}, [])
		start.assert_not_called()
		self.assertEqual(state["status"], "ready")
		self.assertEqual(state["run"], run)
		self.assertEqual(state["output"]["result"], [{"a": 1}])
		self.assertTrue(state["as_of"])

	def test_queued_run_reports_generating(self):
		run = self.make_run({"x": "1"}, "Queued")
		state = prepared_reports.handle(self.report, {"x": 1}, [])
		self.assertEqual((state["status"], state["run"]), ("generating", run))

	def test_failed_run_is_surfaced_with_its_reason_not_rerun(self):
		run = self.make_run({"x": "2"}, "Error")
		frappe.db.set_value("Prepared Report", run, "error_message", TRACEBACK)
		with patch("flow.fac_tools.prepared_reports.start") as start:
			state = prepared_reports.handle(self.report, {"x": "2"}, [])
		start.assert_not_called()
		self.assertEqual(state["status"], "failed")
		self.assertEqual(state["error"], "From Date and To Date are mandatory")
		self.assertIn("From Date and To Date are mandatory", state["message"])

	def test_nothing_usable_starts_a_background_run(self):
		with patch(ENQUEUE):
			state = prepared_reports.handle(self.report, {"x": "3"}, [])
		self.assertEqual(state["status"], "generating")
		self.assertIn("Do not call generate_report again", state["message"])
		self.assertEqual(frappe.db.get_value("Prepared Report", state["run"], "report_name"), self.report)

	def test_no_idle_worker_returns_none_so_the_report_runs_inline(self):
		# The c8mda54eq9 case: the only worker runs this turn, so a background run of a
		# quick report would wait for the turn to end while the turn polled for it.
		with patch.object(prepared_reports, "worker_available", return_value=False), patch(ENQUEUE) as enqueue:
			self.assertIsNone(prepared_reports.handle(self.report, {"x": "5"}, []))
		enqueue.assert_not_called()

	def test_prepared_report_without_idle_worker_answers_inline_in_one_call(self):
		frappe.db.set_value("Report", self.report, "prepared_report", 1)
		output = {"columns": [{"fieldname": "amount", "fieldtype": "Currency"}], "result": [{"amount": 7}]}
		with (
			patch.object(prepared_reports, "worker_available", return_value=False),
			patch("flow.fac_tools.reports.discover_filters", return_value=([], [])),
			patch("frappe.desk.query_report.run", return_value=output) as run,
		):
			result = generate_report(report_name=self.report, filters={"x": "6"})
		run.assert_called_once()
		self.assertNotIn("status", result)
		self.assertEqual((result["data"], result["column_totals"]), ([{"amount": 7}], {"amount": 7}))

	def test_waits_for_the_background_run_and_returns_its_rows(self):
		ready = {"status": "ready", "run": "R"}
		with (
			patch.object(prepared_reports, "WAIT_SECONDS", 5),
			patch.object(prepared_reports, "POLL_SECONDS", 0),
			patch.object(prepared_reports, "_run_status", side_effect=["Queued", "Started", "Completed"]),
			patch.object(prepared_reports, "_read_completed", return_value=ready),
			patch(ENQUEUE),
		):
			state = prepared_reports.handle(self.report, {"x": "7"}, [])
		self.assertIs(state, ready)

	def test_run_failing_during_the_wait_returns_failed_with_reason(self):
		def fail(run):
			frappe.db.set_value("Prepared Report", run, {"status": "Error", "error_message": TRACEBACK})
			return "Error"

		with (
			patch.object(prepared_reports, "WAIT_SECONDS", 5),
			patch.object(prepared_reports, "POLL_SECONDS", 0),
			patch.object(prepared_reports, "_run_status", side_effect=fail),
			patch(ENQUEUE),
		):
			state = prepared_reports.handle(self.report, {"x": "8"}, [])
		self.assertEqual((state["status"], state["error"]), ("failed", "From Date and To Date are mandatory"))

	def test_second_call_in_the_same_turn_does_not_wait_again(self):
		with (
			patch.object(prepared_reports, "WAIT_SECONDS", 0.2),
			patch.object(prepared_reports, "POLL_SECONDS", 0.05),
			patch.object(prepared_reports, "_run_status", return_value="Queued") as status,
			patch(ENQUEUE),
		):
			first = prepared_reports.handle(self.report, {"x": "9"}, [])
			polls = status.call_count
			second = prepared_reports.handle(self.report, {"x": "9"}, [])
		self.assertGreater(polls, 0)
		self.assertEqual(status.call_count, polls)
		self.assertEqual((second["status"], second["run"]), ("generating", first["run"]))
		self.assertIn("Do not call generate_report again", second["message"])

	def test_inline_statement_timeout_moves_report_to_background(self):
		frappe.db.set_value("Report", self.report, {"prepared_report": 0, "disable_prepared_report_automation": 0})
		timeout = pymysql.err.OperationalError(1969, "Query execution was interrupted (max_statement_time exceeded)")
		with patch("frappe.desk.query_report.run", side_effect=timeout), patch(ENQUEUE):
			state = _run_inline(self.report, {"x": "4"}, [])
		self.assertEqual(state["status"], "started")
		self.assertTrue(frappe.db.get_value("Report", self.report, "prepared_report"))


class TestWorkerAvailability(UnitTestCase):
	def check(self, *states):
		workers = []
		for state in states:
			worker = MagicMock()
			worker.queue_names.return_value = [generate_qname("long")]
			worker.get_state.return_value = state
			workers.append(worker)
		in_test, frappe.flags.in_test = frappe.flags.in_test, False
		try:
			with patch("rq.Worker.all", return_value=workers), patch(
				"frappe.utils.background_jobs.get_redis_conn"
			):
				return prepared_reports.worker_available()
		finally:
			frappe.flags.in_test = in_test

	def test_a_busy_worker_is_not_available(self):
		self.assertFalse(self.check("busy"))
		self.assertFalse(self.check())

	def test_an_idle_worker_is_available(self):
		self.assertTrue(self.check("busy", "idle"))


class TestFinancialStatementFilters(IntegrationTestCase):
	def setUp(self):
		if "erpnext" not in frappe.get_installed_apps():
			self.skipTest("ERPNext is not installed")

	def test_profit_and_loss_filters_come_from_the_shared_builder_and_pushes(self):
		filters, diagnostics = discover_filters("Profit and Loss Statement")
		by_name = {row["fieldname"]: row for row in filters}
		self.assertFalse(diagnostics)
		for fieldname in ("company", "filter_based_on", "period_start_date", "periodicity", "selected_view"):
			self.assertIn(fieldname, by_name)
		self.assertNotIn("from_date", by_name)
		self.assertEqual(by_name["filter_based_on"]["default"], "Fiscal Year")
		self.assertEqual(by_name["period_start_date"]["required_when"], "doc.filter_based_on == 'Date Range'")

	def test_conditionally_required_filters_are_enforced(self):
		filters, _ = discover_filters("Profit and Loss Statement")
		with self.assertRaisesRegex(frappe.ValidationError, "period_start_date .required when"):
			apply_defaults({"company": "X", "filter_based_on": "Date Range"}, filters)
		applied = apply_defaults(
			{
				"company": "X",
				"filter_based_on": "Date Range",
				"period_start_date": "2025-04-01",
				"period_end_date": "2026-03-31",
			},
			filters,
		)
		self.assertEqual((applied["periodicity"], applied["selected_view"]), ("Yearly", "Report"))


class TestReportSorting(IntegrationTestCase):
	columns = [
		{"fieldname": "party", "label": "Customer", "fieldtype": "Link"},
		{"fieldname": "outstanding", "label": "Outstanding Amount", "fieldtype": "Currency"},
	]
	rows = [
		{"party": "B", "outstanding": 50},
		{"party": "D", "outstanding": None},
		{"party": "A", "outstanding": 900},
		{"party": "C", "outstanding": 300},
		["Total", 1250],
	]

	def test_sorts_numbers_descending_with_empty_values_last_and_no_total_row(self):
		self.assertEqual([r["party"] for r in sort_rows(self.columns, self.rows, "outstanding")], ["A", "C", "B", "D"])
		self.assertEqual([r["party"] for r in sort_rows(self.columns, self.rows, "outstanding", "asc")], ["B", "C", "A", "D"])

	def test_sort_by_accepts_the_column_label(self):
		self.assertEqual(sort_rows(self.columns, self.rows, "outstanding amount")[0]["party"], "A")
		self.assertEqual([r["party"] for r in sort_rows(self.columns, self.rows, "Customer", "asc")], ["A", "B", "C", "D"])

	def test_unknown_column_lists_the_valid_ones(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Columns: party, outstanding"):
			sort_rows(self.columns, self.rows, "balance")

	def test_tree_report_cannot_be_sorted(self):
		with self.assertRaisesRegex(frappe.ValidationError, "tree"):
			sort_rows(self.columns, [{"party": "X", "outstanding": 1, "indent": 0}], "outstanding")

	def test_top_n_returns_only_those_rows_with_totals_over_all(self):
		report = frappe.db.get_value("Report", {"report_type": "Script Report", "disabled": 0}, "name")
		frappe.db.set_value("Report", report, "prepared_report", 0)
		output = {"columns": self.columns, "result": self.rows}
		with (
			patch("flow.fac_tools.reports.discover_filters", return_value=([], [])),
			patch("frappe.desk.query_report.run", return_value=output),
		):
			result = generate_report(report_name=report, sort_by="outstanding", limit=2)
		self.assertEqual([r["party"] for r in result["data"]], ["A", "C"])
		self.assertEqual((result["data_count"], result["truncated"]), (5, True))
		self.assertEqual(result["column_totals"], {"outstanding": 1250})
		self.assertEqual(result["sorted_by"], "outstanding desc")
		self.assertIn("Showing 2 of 4 rows, sorted by outstanding desc", result["row_note"])

	def test_limit_must_be_positive(self):
		report = frappe.db.get_value("Report", {"report_type": "Script Report", "disabled": 0}, "name")
		frappe.db.set_value("Report", report, "prepared_report", 0)
		with (
			patch("flow.fac_tools.reports.discover_filters", return_value=([], [])),
			patch("frappe.desk.query_report.run", return_value={"columns": self.columns, "result": self.rows}),
			self.assertRaisesRegex(frappe.ValidationError, "limit must be at least 1"),
		):
			generate_report(report_name=report, limit=0)
