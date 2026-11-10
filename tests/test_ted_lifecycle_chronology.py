import json
from pathlib import Path
import unittest
from uuid import UUID

from src.ted_lifecycle_chronology import audit, _uniform_deadline, _publication_day, _relation

P = "93dd47eb-8036-40dd-b3a0-287e1818f0c5"
Q = "8ed8a7d2-ee71-40ce-9267-6475a5e43c95"
OLD = "f8381887-5b8c-4f29-8943-4c380faba9b2"
NEW = "c552d1ec-d98a-47d1-82b3-94c4a1594ea2"
IDS = [f"{600000+i}-2026" for i in range(20)]


def row(number, procedure, notice, **fields):
    return {"publication-number": number, "procedure-identifier": procedure,
            "notice-identifier": notice, "notice-version": 1,
            "publication-date": "2026-09-01+02:00", "form-type": "competition",
            "deadline-receipt-tender-date-lot": ["2026-09-29+02:00"],
            "deadline-receipt-tender-time-lot": ["23:59:00+02:00"], **fields}


def fixture():
    cohort = {"complete_frame_reconciled": True, "cohort_size": 20,
              "notice_items": [{"publication_number": n} for n in IDS]}
    rows = [row(n, str(UUID(int=i+1)), str(UUID(int=i+101))) for i,n in enumerate(IDS)]
    return {"observed_at": "2026-11-10T16:49:21Z", "rows": rows,
            "summary": {"frozen_notice_ids": 20, "frozen_ids_with_metadata": 20,
                        "frozen_rows_identical_across_queries": 20,
                        "procedure_query_notices": 20, "distinct_procedure_ids": 20}}, cohort


class Tests(unittest.TestCase):
    def test_real_linked_change_and_day_boundary(self):
        snap, cohort = fixture()
        snap["rows"][0] = row(IDS[0], P, NEW, **{
            "change-notice-version-identifier": OLD + "-01",
            "deadline-receipt-tender-date-lot": ["2026-09-02Z"],
            "deadline-receipt-tender-time-lot": ["21:59:59Z"]})
        snap["rows"].append(row("417627-2026", P, OLD, **{
            "publication-date": "2026-06-18+02:00",
            "deadline-receipt-tender-date-lot": ["2026-08-31Z"],
            "deadline-receipt-tender-time-lot": ["21:59:59Z"]}))
        snap["summary"]["procedure_query_notices"] = 21
        result = audit(snap, cohort)
        change = result["change_rows"][0]
        self.assertEqual(change["deadline_change_seconds"], 172800)
        self.assertEqual(change["seconds_from_prior_deadline_to_change_publication_day_start"], 1)
        self.assertEqual(change["prior_deadline_vs_change_publication_day"], "before_publication_day")
        self.assertEqual(result["linked_prior_deadlines_before_change_publication_day"], 1)
        self.assertIsNone(result["verified_legal_deadline_errors"])

    def test_uniform_repeated_values_do_not_require_lot_join(self):
        r = row(IDS[0], P, NEW, **{
            "deadline-receipt-tender-date-lot": ["2026-09-29+02:00"]*5,
            "deadline-receipt-tender-time-lot": ["23:59:00+02:00"]*5})
        self.assertEqual(_uniform_deadline(r)[2], "uniform_notice_level_metadata")
        r["deadline-receipt-tender-time-lot"][-1] = "22:00:00+02:00"
        self.assertEqual(_uniform_deadline(r)[2], "nonuniform_projection")
        r["deadline-receipt-tender-time-lot"].pop()
        self.assertEqual(_uniform_deadline(r)[2], "missing_or_unbalanced_projection")

    def test_offset_mismatch_and_multiple_stages_unresolved(self):
        r = row(IDS[0], P, NEW, **{"deadline-receipt-tender-time-lot": ["23:59:00Z"]})
        self.assertEqual(_uniform_deadline(r)[2], "invalid_or_conflicting_offsets")
        r["deadline-receipt-request-date-lot"] = ["2026-09-29+02:00"]
        self.assertEqual(_uniform_deadline(r)[2], "missing_or_multiple_stages")

    def test_clock_rollover_and_offset_overflow_fail_closed(self):
        for date, time, status in (
                ("2026-09-29+02:00", "24:00:00+02:00", "invalid_deadline"),
                ("2026-09-29+02:00", "23:60:00+02:00", "invalid_deadline"),
                ("2026-09-29+02:60", "23:59:00+02:60", "invalid_or_conflicting_offsets"),
                ("2026-09-29+14:01", "23:59:00+14:01", "invalid_or_conflicting_offsets")):
            with self.subTest(date=date, time=time):
                r = row(IDS[0], P, NEW, **{
                    "deadline-receipt-tender-date-lot": [date],
                    "deadline-receipt-tender-time-lot": [time]})
                self.assertEqual(_uniform_deadline(r)[2], status)
                self.assertIsNone(_uniform_deadline(r)[1])
        with self.assertRaises(ValueError):
            _publication_day("2026-09-29+02:60")

    def test_day_interval_not_exact_publication_time(self):
        start, end = _publication_day("2026-09-01+02:00")
        self.assertEqual(_relation(start, start, end), "within_publication_day")
        self.assertEqual(_relation(end, start, end), "after_publication_day")
        self.assertEqual((end-start).total_seconds(), 86400)

    def test_duplicate_and_missing_frozen_fail_closed(self):
        snap, cohort = fixture()
        snap["rows"][1]["publication-number"] = IDS[0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit(snap, cohort)
        snap, cohort = fixture()
        snap["rows"][1]["publication-number"] = "999999-2026"
        with self.assertRaisesRegex(ValueError, "missing frozen"):
            audit(snap, cohort)

    def test_unresolved_reference_not_treated_as_change_comparison(self):
        snap, cohort = fixture()
        snap["rows"][0]["change-notice-version-identifier"] = OLD + "-01"
        result = audit(snap, cohort)
        self.assertEqual(result["change_rows"][0]["status"], "unresolved_reference")
        self.assertEqual(result["linked_change_comparisons"], 0)

    def test_result_interval_not_award_date(self):
        snap, cohort = fixture()
        p = snap["rows"][0]["procedure-identifier"]
        snap["rows"].append(row("729884-2026", p, OLD, **{
            "form-type": "result", "publication-date": "2026-10-21+02:00"}))
        snap["summary"]["procedure_query_notices"] = 21
        result = audit(snap, cohort)
        item = result["result_rows"][0]
        self.assertEqual(item["status"], "single_competition_uniform_tender_metadata")
        self.assertEqual(item["seconds_from_deadline_to_publication_day_end_exclusive"] -
                         item["seconds_from_deadline_to_publication_day_start"], 86400)
        self.assertIsNone(result["verified_agentmine_revenue"])

    def test_multi_notice_result_history_not_silently_selected(self):
        snap, cohort = fixture()
        p = snap["rows"][0]["procedure-identifier"]
        snap["rows"].extend([row("417627-2026", p, OLD), row("729884-2026", p, NEW, **{"form-type":"result"})])
        snap["summary"]["procedure_query_notices"] = 22
        result = audit(snap, cohort)
        self.assertEqual(result["result_rows"][0]["status"], "ambiguous_competition_history")
        self.assertEqual(result["result_publication_interval_comparisons"], 0)

    def test_committed_evidence_snapshot(self):
        root = Path(__file__).resolve().parents[1]
        snapshot = json.loads((root / "data/evidence/ted_fixed20_lifecycle_metadata_2026-11-10.json").read_text())
        cohort = json.loads((root / "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json").read_text())
        result = audit(snapshot, cohort)
        self.assertEqual(result["frozen_notice_count"], 20)
        self.assertEqual(result["lifecycle_notice_count"], 24)
        self.assertEqual(result["uniform_frozen_deadline_count"], 20)
        self.assertEqual(result["frozen_deadlines_before_own_publication_day"], 0)
        self.assertEqual(result["linked_change_comparisons"], 1)
        self.assertEqual(result["linked_prior_deadlines_before_change_publication_day"], 1)
        self.assertEqual(result["change_rows"][0]["seconds_from_prior_deadline_to_change_publication_day_start"], 1)
        self.assertEqual(result["result_publication_interval_comparisons"], 3)
        self.assertIsNone(result["verified_supplier_harm_or_savings"])


if __name__ == "__main__":
    unittest.main()
