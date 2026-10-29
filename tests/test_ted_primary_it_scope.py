"""Guard the fixed TED-20 cohort's main-CPV denominator and pilot interpretation.

The original TED query matches *any* CPV 72 classification, including secondary
ones. Main-CPV IT coverage and the three historical examples must not be
reported as a representative sample of primary-IT supplier decisions.
Only existing public, dated repository evidence is used; no network or buyers.
"""
import json
from pathlib import Path
import unittest

EVIDENCE = Path(__file__).resolve().parents[1] / "data" / "evidence"


def load(filename):
    return json.loads((EVIDENCE / filename).read_text(encoding="utf-8"))


class PrimaryITScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = load("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json")
        cls.projection = load("ted_cpv72_search_projection_summary_2026-10-26.json")
        cls.primary = load("ted_fixed20_primary_portal_stage_2026-10-26.json")
        cls.three = load("ted_fixed20_three_original_deadline_checks_2026-10-28.json")
        cls.four = load("ted_fixed20_four_original_directory_crosschecks_2026-10-28.json")
        cls.portal = load("ted_fixed20_601656_primary_portal_reconciliation_2026-10-28.json")
        cls.option = load("ted_fixed20_615392_option_claim_2026-10-28.json")
        cls.pdf = load("ted_601730_primary_pdf_2026-10-29.json")
        cls.preflights = load("ted_three_historical_supplier_preflights_2026-10-26.json")

    def test_primary_it_coverage_excludes_secondary_only_cpv72_notices(self):
        frozen = {row["publication_number"] for row in self.cohort["notice_items"]}
        by_id = {row["publication_number"]: row["procedure_main_cpv"]
                 for row in self.projection["rows"]}
        self.assertEqual(set(by_id), frozen)
        primary_it = {notice for notice, cpv in by_id.items()
                      if cpv.startswith(("48", "72"))}
        other = frozen - primary_it
        self.assertEqual(len(frozen), 20)
        self.assertEqual(len(primary_it), 17)
        self.assertEqual(other, {"600201-2026", "601453-2026", "610120-2026"})

        reviewed = (
            {row["publication_number"] for row in self.cohort["notice_items"]
             if row["original_notice_checked"]}
            | {row["publication_number"] for row in self.primary["observations"]}
            | {row["publication_number"] for row in self.three["new_notices"]}
            | {row["publication_number"] for row in self.four["observations"]}
            | {self.portal["notice"]["publication_number"],
               self.option["audit_input"]["publication_number"],
               self.pdf["publication_number"]}
        )
        self.assertEqual(len(reviewed), 16)
        self.assertEqual(len(reviewed & primary_it), 14)
        self.assertEqual(primary_it - reviewed,
                         {"612757-2026", "613749-2026", "615414-2026"})
        self.assertEqual(reviewed & other, {"600201-2026", "610120-2026"})
        self.assertEqual(other - reviewed, {"601453-2026"})

    def test_historical_examples_do_not_satisfy_three_primary_it_supplier_trials(self):
        examples = self.preflights["examples"]
        self.assertEqual(len(examples), 3)
        by_id = {row["publication_number"]: row["procedure_main_cpv"]
                 for row in self.projection["rows"]}
        for example in examples:
            self.assertEqual(example["main_cpv"], by_id[example["publication_number"]])
            self.assertIs(example["primary_it_cpv_48_or_72"],
                          example["main_cpv"].startswith(("48", "72")))
            self.assertEqual(example["supplier_bid_no_bid"], "UNDETERMINED")
            self.assertIs(example["historical_not_live_opportunity"], True)
        self.assertEqual([e["publication_number"] for e in examples
                          if e["primary_it_cpv_48_or_72"]], ["603727-2026"])
        self.assertEqual(self.preflights["actual_paired_supplier_tasks"], 0)
        self.assertEqual(self.preflights["explicit_price_or_pilot_responses"], 0)
        self.assertIsNone(self.preflights["verified_paying_customers"])


if __name__ == "__main__":
    unittest.main()
