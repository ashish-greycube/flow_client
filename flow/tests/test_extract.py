# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.tests import UnitTestCase

from flow.knowledge.extract import FILE_EXTENSIONS, _looks_like_prose


class TestDocExtensionSupported(UnitTestCase):
	def test_legacy_doc_extension_is_supported(self):
		self.assertIn("doc", FILE_EXTENSIONS)


class TestLooksLikeProse(UnitTestCase):
	def test_accepts_natural_language_sentence(self):
		self.assertTrue(_looks_like_prose("Employee Name: John Smith, Position Title: Manager"))

	def test_rejects_short_run(self):
		self.assertFalse(_looks_like_prose("JFIF"))

	def test_rejects_run_without_word_boundaries(self):
		self.assertFalse(_looks_like_prose("XICC_PROFILEHLinomntrRGB"))

	def test_rejects_symbol_heavy_binary_noise(self):
		self.assertFalse(_looks_like_prose("br0$U$-;DsDm8&7>83mKy"))
