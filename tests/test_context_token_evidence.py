import copy
import json
from pathlib import Path
import unittest

from src.context_token_evidence import analyze


FIXTURE = Path(__file__).resolve().parents[1] / "data/evidence/agent_context_token_overhead_2026-10-24.json"


class ContextTokenEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_real_public_issue_cases_are_attributed(self):
        result = analyze(self.snapshot)
        self.assertEqual(result["case_count"], 7)
        self.assertEqual(len({c["source_url"] for c in result["cases"]}), 2)
        self.assertTrue(all(c["source_url"].startswith("https://github.com/") for c in result["cases"]))

    def test_exact_same_job_cohort_is_not_mixed_with_approximate_or_other_modes(self):
        result = analyze(self.snapshot)
        self.assertEqual(result["exact_count_same_job_configuration_change"], 3)
        self.assertEqual(result["exact_same_job_reported_reduction_pct_range"], ["91.36", "91.87"])
        self.assertEqual(result["cases"][5]["reported_token_difference_pct"], "92.57")
        self.assertEqual(result["cases"][5]["comparison_type"], "different_delivery_modes")

    def test_never_infer_paid_demand_or_independently_verified_savings(self):
        result = analyze(self.snapshot)
        for key in ("independently_verified_token_savings", "verified_cost_savings_usd",
                    "verified_paying_customers", "verified_willingness_to_pay"):
            self.assertIsNone(result[key])
        self.assertTrue(all(not c["output_equivalence_verified"] for c in result["cases"]))

    def test_reject_boolean_or_invalid_token_counts(self):
        for before, after in [(True, 1), (100, False), (0, 1), (-1, 1), (1, -1), (1.0, 1)]:
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["sources"][0]["comparisons"][0].update(before_tokens=before, after_tokens=after)
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                analyze(snapshot)

    def test_reject_duplicate_ids_across_sources(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["sources"][1]["comparisons"][0]["id"] = snapshot["sources"][0]["comparisons"][0]["id"]
        with self.assertRaises(ValueError):
            analyze(snapshot)

    def test_reject_unattributed_or_noncanonical_issue_sources(self):
        for url in ("http://github.com/owner/repo/issues/1", "https://evil.com/issues/1",
                    "https://github.com/owner/repo", "https://github.com/owner/repo/issues/1?token=x"):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["sources"][0]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                analyze(snapshot)

    def test_reject_ambiguous_classification(self):
        for key, value in (("approximate", 0), ("comparison_type", "verified_savings")):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["sources"][0]["comparisons"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(snapshot)


if __name__ == "__main__":
    unittest.main()
