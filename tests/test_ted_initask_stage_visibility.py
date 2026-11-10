"""Replay the actual frozen TED metadata and public Initask observations."""
import copy
import json
from pathlib import Path
import unittest

from src.ted_initask_stage_visibility import audit, EVIDENCE_PATH, SNAPSHOT_PATH, COHORT_PATH

ROOT = Path(__file__).resolve().parents[1]


class InitaskStageVisibilityTests(unittest.TestCase):
    def setUp(self):
        load = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))
        self.snapshot = load(SNAPSHOT_PATH)
        self.cohort = load(COHORT_PATH)
        self.evidence = load(EVIDENCE_PATH)

    def run_audit(self):
        return audit(self.snapshot, self.cohort, self.evidence)

    def row(self, number):
        return next(r for r in self.evidence["rows"] if r["publication_number"] == number)

    def test_actual_fixed_cohort_denominators(self):
        result = self.run_audit()
        self.assertEqual((result["frozen_notice_count"], result["rendered_count"],
                          result["unavailable_count"]), (20, 14, 6))
        request = result["by_stage"]["participation"]
        tender = result["by_stage"]["tender"]
        self.assertEqual((request["attempted"], request["rendered"], request["unavailable"],
                          request["no_deadline_visible"], request["deadline_visible"]), (8, 5, 3, 5, 0))
        self.assertEqual((tender["attempted"], tender["rendered"], tender["unavailable"],
                          tender["no_deadline_visible"], tender["deadline_visible"]), (12, 9, 3, 0, 9))

    def test_actual_offsetless_clock_comparison(self):
        tender = self.run_audit()["by_stage"]["tender"]
        self.assertEqual((tender["offset_not_visible"], tender["source_clock_matches"],
                          tender["stockholm_clock_matches"], tender["utc_clock_only_matches"]), (9, 9, 6, 3))

    def test_actual_unknowns_not_counted_as_omissions(self):
        result = self.run_audit()
        self.assertEqual({r["publication_number"] for r in result["items"]
                          if r["classification"] == "unavailable_unknown"},
                         {"600201-2026", "601453-2026", "601730-2026",
                          "605974-2026", "606049-2026", "612757-2026"})
        self.assertIsNone(result["verified_legal_deadline_errors"])
        self.assertIsNone(result["verified_agentmine_revenue"])
        self.assertEqual(result["new_portal_corroborations"], 0)

    def test_duplicate_and_missing_fail_closed(self):
        self.evidence["rows"][-1] = copy.deepcopy(self.evidence["rows"][0])
        with self.assertRaises(ValueError):
            self.run_audit()
        self.evidence["rows"].pop()
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_unavailable_cannot_claim_a_deadline(self):
        self.row("612757-2026")["displayed_minute"] = "2026-10-05T00:00"
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_missing_deadline_needs_empty_lot_fields(self):
        self.row("603727-2026")["lot_deadline_cells_empty"] = False
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_source_binding_and_url(self):
        self.evidence["source_observed_at"] = "2026-11-09T00:00:00Z"
        with self.assertRaises(ValueError):
            self.run_audit()
        self.evidence["source_observed_at"] = self.snapshot["observed_at"]
        self.row("603727-2026")["source_url"] = "https://eutenders.initask.com/notice/606049-2026"
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_wrong_clock_is_not_silently_matched(self):
        self.row("611111-2026")["displayed_minute"] = "2026-10-06T22:59"
        tender = self.run_audit()["by_stage"]["tender"]
        self.assertEqual(tender["source_clock_matches"], 8)
        self.assertEqual(tender["utc_clock_only_matches"], 2)

    def test_invalid_or_offset_bearing_clock_rejected(self):
        self.row("611111-2026")["displayed_minute"] = "2026-10-06T25:00"
        with self.assertRaises(ValueError):
            self.run_audit()
        self.row("611111-2026")["displayed_minute"] = "2026-10-06T21:59"
        self.row("611111-2026")["displayed_offset"] = "Z"
        with self.assertRaises(ValueError):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
