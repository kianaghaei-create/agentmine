"""Synthetic mutation regressions and one dated public-source fixture."""
import copy
import json
from pathlib import Path
import unittest

from src.notice_lineage_exception import analyze

ROOT = Path(__file__).resolve().parents[1]


class NoticeLineageExceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/evidence/kriminalvarden_notice_lineage_2026-10-30.json").read_text())

    def test_real_public_directory_display_and_third_party_lineage(self):
        r = analyze(self.data)
        self.assertEqual(r["directory_listings"], 2)
        self.assertEqual(r["older_directory_amount_sek"], "1800000000")
        self.assertEqual(r["newer_directory_amount_sek"], "50000000")
        self.assertEqual(r["older_to_newer_display_ratio"], "36")
        self.assertEqual(r["naively_summed_directory_amount_sek"], "1850000000")
        self.assertEqual(r["naive_sum_to_newer_display_ratio"], "37")
        self.assertEqual(r["independent_third_party_lineage_claim_sources"], 2)
        self.assertIsNone(r["verified_current_legal_contract_value_sek"])
        self.assertIsNone(r["population_prevalence"])
        self.assertIsNone(r["verified_agentmine_revenue_sek"])

    def test_missing_or_duplicate_claims_fail_closed(self):
        for claims in ([], [self.data["lineage_claim_sources"][0]] * 2):
            with self.subTest(claims=claims):
                data = copy.deepcopy(self.data)
                data["lineage_claim_sources"] = claims
                with self.assertRaises(ValueError):
                    analyze(data)

    def test_wrong_source_host_or_notice_fails_closed(self):
        for url in ("https://evil.example/en/tender/725675-2026",
                    "https://upphandla.app/en/tender/729380-2026"):
            data = copy.deepcopy(self.data)
            data["directory_notice_pages"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                analyze(data)

    def test_different_buyer_deadline_or_cpv_fails_closed(self):
        for field, value in (("buyer", "Other"), ("deadline", "2026-11-24"), ("cpv", ["72000000"])):
            data = copy.deepcopy(self.data)
            data["directory_notice_pages"][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze(data)

    def test_rejects_unverified_commercial_promotions(self):
        for field, value in (("official_primary_verified", True),
                             ("verified_agentmine_revenue_sek", "100"),
                             ("verified_supplier_savings", "10")):
            data = copy.deepcopy(self.data)
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze(data)

    def test_rejects_non_decimal_amount_and_wrong_chronology(self):
        for amount in ("1e9", "-1", "NaN", 1800000000):
            data = copy.deepcopy(self.data)
            data["directory_notice_pages"][0]["value_sek"] = amount
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                analyze(data)
        data = copy.deepcopy(self.data)
        data["directory_notice_pages"][1]["published"] = "2026-10-18"
        with self.assertRaises(ValueError):
            analyze(data)

    def test_rejects_impossible_calendar_dates(self):
        for field, value in (("deadline", "2026-02-30"),
                             ("published", "2026-02-30"),
                             ("published", "20261020")):
            data = copy.deepcopy(self.data)
            data["directory_notice_pages"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                analyze(data)
        for observed in ("2026-02-30", "20261030"):
            data = copy.deepcopy(self.data)
            data["observed_date"] = observed
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                analyze(data)

    def test_rejects_publication_after_observation(self):
        data = copy.deepcopy(self.data)
        data["observed_date"] = "2026-10-19"
        with self.assertRaisesRegex(ValueError, "postdates"):
            analyze(data)

    def test_future_dated_observation_cannot_validate_directory_lineage(self):
        # The two directory rows may be real, but an observation cannot be
        # claimed in a year that has not yet occurred.
        data = copy.deepcopy(self.data)
        data["observed_date"] = "2099-12-31"
        with self.assertRaisesRegex(ValueError, "future"):
            analyze(data)

    def test_cross_publisher_claim_binding(self):
        data = copy.deepcopy(self.data)
        data["lineage_claim_sources"][0]["url"] = "https://tenderiva.com/sv/tender/725675-2026-other"
        with self.assertRaisesRegex(ValueError, "Tenderiva notice"):
            analyze(data)
        data = copy.deepcopy(self.data)
        data["lineage_claim_sources"][1]["assertion"] = "verified_legal_deadline"
        with self.assertRaises(ValueError):
            analyze(data)


    def test_generic_other_public_notice_pair_uses_same_audit(self):
        data = copy.deepcopy(self.data)
        older, newer = data["directory_notice_pages"]
        older["notice_id"] = "123456-2026"
        older["url"] = "https://upphandla.app/en/tender/123456-2026"
        newer["notice_id"] = "123457-2026"
        newer["url"] = "https://upphandla.app/en/tender/123457-2026"
        for row in (older, newer):
            row["buyer"] = "Another Public Authority"
            row["title"] = "A different software system"
            row["deadline"] = "2026-12-01"
            row["cpv"] = ["48000000"]
        data["lineage_claim_sources"][0]["assertion"] = "correction_notice_of_123456-2026"
        data["lineage_claim_sources"][0]["url"] = "https://tenderiva.com/sv/tender/123457-2026-other-system"
        data["lineage_claim_sources"][1]["url"] = "https://licitera.se/upphandling/other-system-1234"
        result = analyze(data)
        self.assertEqual(result["older_to_newer_display_ratio"], "36")
        self.assertIsNone(result["verified_current_legal_contract_value_sek"])

if __name__ == "__main__":
    unittest.main()
