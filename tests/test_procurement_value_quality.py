"""Regression tests for the source-attributed CPV48 tender quality gate.

These tests use synthetic fixtures only. They do not demonstrate live demand,
award value, customer willingness to pay, or actual market coverage.
"""
import copy
import unittest

from src.procurement_value_quality import analyze


AS_OF = "2026-10-18"


def row(**overrides):
    result = {
        "ted_publication_number": "718613-2026",
        "source_url": "https://licitera.se/upphandling/asset-data-platform",
        "buyer": "Example buyer",
        "cpv": ["48000000"],
        "estimated_value_sek": 96000000,
        "deadline": "2026-10-19",
    }
    result.update(overrides)
    return result


def snapshot(*rows):
    return {"license": "CC BY 4.0", "source_publisher": "Licitera",
            "sample_selection": "synthetic regression fixtures", "records": list(rows)}


class ProcurementValueQualityTests(unittest.TestCase):
    def run_one(self, **overrides):
        return analyze(snapshot(row(**overrides)), as_of=AS_OF)

    def test_future_deadline_eligible_with_sufficient_estimate(self):
        result = self.run_one()
        self.assertEqual(result["eligible_for_automatic_value_ranking_count"], 1)
        self.assertTrue(result["records"][0]["eligible_for_automatic_value_ranking"])
        self.assertEqual(result["records"][0]["quality_flags"], [])

    def test_same_day_unknown_time_is_never_automatically_eligible(self):
        result = self.run_one(deadline=AS_OF)
        self.assertEqual(result["eligible_for_automatic_value_ranking_count"], 0)
        self.assertEqual(result["records"][0]["quality_flags"],
                         ["deadline_today_time_unknown_review_required"])

    def test_expired_deadline_is_never_automatically_eligible(self):
        result = self.run_one(deadline="2026-10-17")
        self.assertEqual(result["eligible_for_automatic_value_ranking_count"], 0)
        self.assertIn("deadline_elapsed_as_of_date", result["records"][0]["quality_flags"])

    def test_missing_estimate_is_flagged_not_ranked(self):
        result = self.run_one(estimated_value_sek=None)
        self.assertEqual(result["eligible_for_automatic_value_ranking_count"], 0)
        self.assertIn("estimate_missing", result["records"][0]["quality_flags"])

    def test_low_estimate_requires_review_even_when_future(self):
        for value in (0, 999):
            with self.subTest(value=value):
                result = self.run_one(estimated_value_sek=value)
                self.assertEqual(result["low_estimate_review_count"], 1)
                self.assertFalse(result["records"][0]["eligible_for_automatic_value_ranking"])

    def test_threshold_is_inclusive(self):
        result = self.run_one(estimated_value_sek="1000")
        self.assertEqual(result["eligible_for_automatic_value_ranking_count"], 1)

    def test_flags_can_coexist_without_automatic_ranking(self):
        result = self.run_one(deadline=AS_OF, estimated_value_sek="999")
        self.assertEqual(result["low_estimate_review_count"], 1)
        self.assertEqual(len(result["records"][0]["quality_flags"]), 2)
        self.assertEqual(result["eligible_for_automatic_value_ranking_count"], 0)

    def test_rejects_duplicate_ted_publication_number(self):
        with self.assertRaisesRegex(ValueError, "duplicate TED"):
            analyze(snapshot(row(), copy.deepcopy(row())), as_of=AS_OF)

    def test_rejects_untrusted_source_urls(self):
        for url in ("http://licitera.se/upphandling/a",
                    "https://licitera.se.evil.test/upphandling/a",
                    "https://attacker@licitera.se/upphandling/a",
                    "https://licitera.se/elsewhere/a"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "untrusted source URL"):
                self.run_one(source_url=url)

    def test_rejects_invalid_cpv_and_non48_category(self):
        for cpv in ([], ["48"], [48000000], ["72000000"], "48000000"):
            with self.subTest(cpv=cpv), self.assertRaises(ValueError):
                self.run_one(cpv=cpv)

    def test_rejects_invalid_values(self):
        for value in (True, -1, 1.5, "NaN", "Infinity", "1000.1", "oops"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_one(estimated_value_sek=value)

    def test_rejects_invalid_dates(self):
        for deadline in (None, "2026-02-30", "tomorrow", 20261019):
            with self.subTest(deadline=deadline), self.assertRaisesRegex(ValueError, "invalid deadline"):
                self.run_one(deadline=deadline)
        for as_of in (None, "2026-13-18", 20261018):
            with self.subTest(as_of=as_of), self.assertRaisesRegex(ValueError, "as_of must be"):
                analyze(snapshot(row()), as_of=as_of)

    def test_rejects_missing_or_unlicensed_evidence(self):
        for field, value in (("license", "unknown"), ("source_publisher", "unknown"),
                             ("records", None)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence = snapshot(row())
                evidence[field] = value
                analyze(evidence, as_of=AS_OF)

    def test_rejects_malformed_publication_reference(self):
        for ref in ("718613", "foo-2026", "718613-1999", "718613-2026 "):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "invalid TED reference"):
                self.run_one(ted_publication_number=ref)

    def test_no_verified_commercial_claims(self):
        result = self.run_one()
        self.assertIsNone(result["verified_supplier_demand"])
        self.assertIsNone(result["verified_agentmine_revenue"])
        self.assertIn("Convenience sample", result["warning"])


if __name__ == "__main__":
    unittest.main()
