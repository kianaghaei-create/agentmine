"""Integration tests against the committed public evidence, not synthetic demand."""
import copy
import json
from pathlib import Path
import unittest

from src.procurement_source_quality_feed import INPUT_PATHS, build, from_root


class SourceQualityFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in INPUT_PATHS]
        cls.report = from_root()
        cls.rows = {r["publication_number"]: r for r in cls.report["records"]}

    def test_full_frozen_cohort_and_overlap(self):
        r = self.report
        self.assertEqual(r["fixed_notice_count"], 20)
        self.assertEqual(len(self.rows), 20)
        self.assertEqual(r["both_directories_rendered_count"], 14)
        self.assertEqual(r["both_directories_omit_deadline_count"], 5)
        self.assertEqual(r["both_omit_notice_ids"], [
            "603727-2026", "609559-2026", "609601-2026", "610120-2026", "615414-2026"])

    def test_paired_date_labels_are_not_all_errors(self):
        r = self.report
        self.assertEqual(r["paired_date_labels_count"], 9)
        self.assertEqual(r["paired_date_relation_counts"], {
            "different_upphandla_neither_utc_nor_stockholm": 4,
            "different_utc_stockholm_compatible": 2,
            "not_comparable": 11, "same_calendar_label": 3})
        self.assertEqual(r["previously_inspected_original_instants_reconciled"], 11)
        self.assertEqual(r["review_code_counts"]["upphandla_date_not_utc_or_stockholm"], 5)

    def test_midnight_is_context_not_error(self):
        for n in ("605974-2026", "613749-2026", "615576-2026"):
            row = self.rows[n]
            self.assertEqual(row["upphandla"]["date_relation"], "utc_date_only_compatible")
            self.assertEqual(row["context_codes"], ["date_only_timezone_ambiguity"])
            self.assertFalse(row["historical_review_required"])

    def test_utc_clock_risk_and_same_date(self):
        for n in ("611111-2026", "613716-2026", "615392-2026"):
            row = self.rows[n]
            self.assertEqual(row["cross_provider_date_relation"], "same_calendar_label")
            self.assertIn("initask_utc_only_offsetless_clock", row["review_codes"])
            self.assertIsNone(row["initask"]["visible_offset"])

    def test_selected_counterexamples_and_unavailable(self):
        self.assertEqual(self.report["selected_tilldelat_participation_date_matches"], 4)
        self.assertEqual(self.report["selected_tilldelat_matches_where_both_omit"], 3)
        row = self.rows["606049-2026"]
        self.assertEqual(row["initask"]["status"], "unavailable_unknown")
        self.assertNotIn("initask_published_stage_deadline_not_visible", row["review_codes"])
        self.assertTrue(row["tilldelat_selected_comparator"]["explicit_participation_date_matches_stockholm"])

    def test_linked_procedure_not_double_counted(self):
        row = self.rows["601453-2026"]
        self.assertEqual(row["upphandla"]["status"], "page_unavailable")
        self.assertEqual(row["initask"]["status"], "unavailable_unknown")
        self.assertEqual(row["review_codes"], ["linked_procedure_headline_history_conflict"])
        linked = row["linked_change_selected_comparison"]
        self.assertEqual(linked["prior_notice_id"], "417627-2026")
        self.assertEqual(len(linked["procedure_pages"]), 2)
        self.assertNotIn("417627-2026", self.rows)
        self.assertEqual(self.report["historical_review_notice_count"], 17)

    def test_no_commercial_or_legal_claims(self):
        for row in self.rows.values():
            self.assertFalse(row["operative_deadline_verified"])
        for k in ("verified_legal_deadline_errors", "verified_supplier_outcomes",
                  "verified_agentmine_revenue"):
            self.assertIsNone(self.report[k])
        self.assertEqual(self.report["new_original_or_portal_inspections"], 0)

    def test_cross_snapshot_procedure_mismatch_rejected(self):
        args = copy.deepcopy(self.inputs)
        args[2]["rows"][0]["procedure_identifier"] = args[2]["rows"][1]["procedure_identifier"]
        with self.assertRaisesRegex(ValueError, "cross-snapshot"):
            build(*args)

    def test_original_instant_mismatch_rejected(self):
        args = copy.deepcopy(self.inputs)
        args[5]["attempts"][0]["official_original_datetime"] = "2026-09-29T22:59:00+02:00"
        with self.assertRaisesRegex(ValueError, "original instant"):
            build(*args)

    def test_original_display_mismatch_rejected(self):
        args = copy.deepcopy(self.inputs)
        args[5]["attempts"][0]["directory_display_date"] = "2026-09-29"
        with self.assertRaisesRegex(ValueError, "original instant"):
            build(*args)

    def test_missing_original_comparison_rejected(self):
        args = copy.deepcopy(self.inputs)
        args[5]["attempts"].pop()
        with self.assertRaisesRegex(ValueError, "cover every"):
            build(*args)

    def test_stale_chronology_rejected(self):
        args = copy.deepcopy(self.inputs)
        args[6]["source_observed_at"] = "2026-11-09T16:49:21.074404+00:00"
        args[7]["source_observed_at"] = args[6]["source_observed_at"]
        with self.assertRaisesRegex(ValueError, "chronology snapshot"):
            build(*args)


if __name__ == "__main__":
    unittest.main()
