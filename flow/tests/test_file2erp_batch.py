# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.api.file2erp import (
	create_combined_expense_claim,
	create_document_from_entry,
	get_file2erp_batch,
	remove_from_batch,
	start_batch,
)


class TestFile2ERPBatch(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("DocType", "Expense Claim"):
			self.skipTest("HRMS is not installed")
		self.entries = [self.entry(f"receipt-{i}.txt") for i in (1, 2, 3)]

	def tearDown(self):
		frappe.db.rollback()

	def entry(self, file_name: str) -> str:
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": b"receipt text", "is_private": 1}
		).insert(ignore_permissions=True)
		return (
			frappe.get_doc({"doctype": "Flow File2ERP", "file": file_doc.name, "file_name": file_name})
			.insert(ignore_permissions=True)
			.name
		)

	def extracted(self, name: str, remark: str, rows: list[dict], status: str = "Extracted"):
		employee = frappe.db.get_value(
			"Employee", {"status": "Active", "expense_approver": ["is", "set"]}, ["name", "company"], as_dict=True
		)
		if not employee:
			self.skipTest("No active Employee with an expense approver")
		# Shaped as expense_claim_extraction leaves it: the uploader's employee, company and
		# the company's currency at an exchange rate of 1.
		fields = {
			"employee": employee.name,
			"company": employee.company,
			"currency": frappe.db.get_value("Company", employee.company, "default_currency"),
			"exchange_rate": 1.0,
			"remark": remark,
		}
		frappe.db.set_value(
			"Flow File2ERP",
			name,
			{
				"status": status,
				"extracted_fields": json.dumps(fields),
				"extracted_line_items": json.dumps(rows),
			},
		)

	def start(self, mode: str, document_type: str = "Expense Claim"):
		with patch("frappe.enqueue") as enqueue:
			result = start_batch(self.entries, document_type, mode)
		self.assertEqual(enqueue.call_count, len(self.entries))
		return result

	def expense(self, amount: float) -> dict:
		expense_type = frappe.db.get_value("Expense Claim Type", {}, "name")
		return {"expense_date": "2026-10-01", "expense_type": expense_type, "description": "Taxi", "amount": amount}

	def test_separate_mode_starts_every_file_as_its_own_document(self):
		result = self.start("separate", "Purchase Invoice")
		self.assertIsNone(result["batch"])
		for name in self.entries:
			row = frappe.db.get_value("Flow File2ERP", name, ["document_type", "batch"], as_dict=True)
			self.assertEqual((row.document_type, row.batch), ("Purchase Invoice", None))

	def test_combined_mode_is_only_for_expense_claims(self):
		with patch("frappe.enqueue"), self.assertRaisesRegex(frappe.ValidationError, "Only Expense Claims"):
			start_batch(self.entries, "Purchase Invoice", "combined")

	def test_an_already_processed_file_cannot_join_a_batch(self):
		frappe.db.set_value("Flow File2ERP", self.entries[0], "status", "Extracted")
		with patch("frappe.enqueue"), self.assertRaisesRegex(frappe.ValidationError, "already been processed"):
			start_batch(self.entries, "Expense Claim", "combined")

	def test_batch_merges_header_and_rows_from_every_file(self):
		batch = self.start("combined")["batch"]
		self.extracted(self.entries[0], "Airport taxi", [self.expense(500)])
		self.extracted(self.entries[1], "", [self.expense(120), self.expense(80)])
		self.extracted(self.entries[2], "Team lunch", [self.expense(900)])

		data = get_file2erp_batch(batch)
		self.assertEqual(data["not_ready"], [])
		self.assertEqual(data["fields"]["remark"], "receipt-1.txt: Airport taxi\nreceipt-3.txt: Team lunch")
		self.assertTrue(data["fields"]["employee"])
		self.assertEqual(
			[(row["file"], row["amount"]) for row in data["line_items"]],
			[("receipt-1.txt", 500), ("receipt-2.txt", 120), ("receipt-2.txt", 80), ("receipt-3.txt", 900)],
		)
		self.assertEqual([e["expense_rows"] for e in data["entries"]], [1, 2, 1])

	def test_claim_waits_for_every_file(self):
		batch = self.start("combined")["batch"]
		self.extracted(self.entries[0], "Taxi", [self.expense(500)])
		self.extracted(self.entries[1], "", [], status="Failed")
		frappe.db.set_value("Flow File2ERP", self.entries[2], "status", "Processing")

		reasons = get_file2erp_batch(batch)["not_ready"]
		self.assertEqual(len(reasons), 2)
		self.assertIn("receipt-2.txt could not be read", reasons[0])
		self.assertIn("receipt-3.txt is still being read", reasons[1])
		with self.assertRaisesRegex(frappe.ValidationError, "could not be read"):
			create_combined_expense_claim(batch)

	def test_a_read_file_without_expense_rows_blocks_the_claim(self):
		batch = self.start("combined")["batch"]
		self.extracted(self.entries[0], "Taxi", [self.expense(500)])
		self.extracted(self.entries[1], "", [])
		self.extracted(self.entries[2], "Lunch", [self.expense(900)])
		self.assertEqual(
			get_file2erp_batch(batch)["not_ready"],
			["receipt-2.txt has no expense rows: fix it on its own page or remove it from the claim."],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "no expense rows"):
			create_combined_expense_claim(batch)

	def test_removed_file_leaves_the_claim_and_stands_alone(self):
		batch = self.start("combined")["batch"]
		self.extracted(self.entries[0], "Taxi", [self.expense(500)])
		self.extracted(self.entries[1], "", [], status="Failed")
		self.extracted(self.entries[2], "Lunch", [self.expense(900)])

		remove_from_batch(self.entries[1])
		data = get_file2erp_batch(batch)
		self.assertEqual([e["name"] for e in data["entries"]], [self.entries[0], self.entries[2]])
		self.assertEqual(data["not_ready"], [])
		self.assertIsNone(frappe.db.get_value("Flow File2ERP", self.entries[1], "batch"))

	def test_a_file_in_a_batch_cannot_be_created_on_its_own(self):
		self.start("combined")
		self.extracted(self.entries[0], "Taxi", [self.expense(500)])
		with self.assertRaisesRegex(frappe.ValidationError, "part of a combined Expense Claim"):
			create_document_from_entry(self.entries[0], "Expense Claim")

	def test_creates_one_claim_with_every_row_and_links_every_file(self):
		batch = self.start("combined")["batch"]
		self.extracted(self.entries[0], "Taxi", [self.expense(500)])
		self.extracted(self.entries[1], "", [self.expense(120), self.expense(80)])
		self.extracted(self.entries[2], "Lunch", [self.expense(900)])

		response = create_combined_expense_claim(batch)
		created = response["result"]["created"]
		self.assertEqual(response["result"].get("failures") or [], [], response)
		self.assertEqual(len(created), 1)
		claim = frappe.get_doc("Expense Claim", created[0])
		self.assertEqual([row.amount for row in claim.expenses], [500, 120, 80, 900])
		self.assertEqual(claim.total_claimed_amount, 1600)
		for name in self.entries:
			row = frappe.db.get_value("Flow File2ERP", name, ["status", "created_document"], as_dict=True)
			self.assertEqual((row.status, row.created_document), ("Document Created", claim.name))
		attached = frappe.get_all(
			"File", filters={"attached_to_doctype": "Expense Claim", "attached_to_name": claim.name}, pluck="file_name"
		)
		self.assertEqual(sorted(attached), ["receipt-1.txt", "receipt-2.txt", "receipt-3.txt"])

		data = get_file2erp_batch(batch)
		self.assertEqual((data["created_document"], data["not_ready"]), (claim.name, []))
		with self.assertRaisesRegex(frappe.ValidationError, "already part of a created document"):
			create_combined_expense_claim(batch)

	def test_reviewed_rows_replace_the_extracted_ones(self):
		batch = self.start("combined")["batch"]
		for name in self.entries:
			self.extracted(name, "", [self.expense(100)])
		data = get_file2erp_batch(batch)
		rows = data["line_items"][:2]
		rows[0]["amount"] = 250

		response = create_combined_expense_claim(batch, data["fields"], rows)
		claim = frappe.get_doc("Expense Claim", response["result"]["created"][0])
		self.assertEqual([row.amount for row in claim.expenses], [250, 100])

	def test_claim_without_rows_is_refused(self):
		batch = self.start("combined")["batch"]
		for name in self.entries:
			self.extracted(name, "", [self.expense(100)])
		response = create_combined_expense_claim(batch, get_file2erp_batch(batch)["fields"], [])
		self.assertEqual(response["result"]["created"], [])
		self.assertIn("at least one expense row", response["missing_mandatory"])
