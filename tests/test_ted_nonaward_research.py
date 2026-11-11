import unittest
import json
from pathlib import Path

from src.ted_nonaward_research import QUERY, classify, review, run, replay, _uniform_status, _uniform_closed_reason, followup


def row(**changes):
    return {"publication-number": "729884-2026", "publication-date": "2026-10-21+02:00",
            "notice-type": "can-standard", "form-type": "result", "buyer-country": ["SWE"],
            "classification-cpv": ["72000000"], "main-classification-proc": "72000000",
            "procedure-identifier": "b5cc9d60-5185-4d2d-8252-c68ccc6b8b56",
            "identifier-lot": ["LOT-0000"], "result-lot-identifier": ["LOT-0000"],
            "winner-selection-status": ["clos-nw"], "non-award-justification": ["no-rece"],
            "received-submissions-type-code": ["tenders"], "received-submissions-type-val": ["0"],
            "buyer-name": "Synthetic fixture", "notice-title": "Synthetic fixture", **changes}


class NonAwardResearchTests(unittest.TestCase):
    def test_zero_tender_and_relaunch_not_live_need(self):
        r = classify(row(**{"procurement-relaunch-proc": "true"}))
        self.assertEqual(r["classification"], "closed_no_submissions_count_zero")
        self.assertTrue(r["procedure_relaunch_reported_true"])
        self.assertIsNone(r["current_need_verified"])

    def test_closed_other_reason_with_bids(self):
        r = classify(row(**{"non-award-justification": ["all-rej"],
                            "received-submissions-type-val": ["3"]}))
        self.assertEqual(r["classification"], "closed_other_reason")
        self.assertEqual(r["total_tenders_reported"], 3)

    def test_conflicting_positive_count(self):
        r = classify(row(**{"received-submissions-type-val": ["3"]}))
        self.assertEqual(r["classification"], "closed_no_submissions_count_conflict")

    def test_no_parallel_array_join(self):
        r = classify(row(**{"received-submissions-type-code": ["tenders", "t-sme"],
                            "received-submissions-type-val": ["0", "0"]}))
        self.assertEqual(r["classification"], "closed_no_submissions_reason_only")
        self.assertIsNone(r["total_tenders_reported"])

    def test_multiple_result_lots_remain_unjoined(self):
        r = classify(row(**{"result-lot-identifier": ["LOT-0000", "LOT-0001"],
                            "winner-selection-status": ["clos-nw", "selec-w"]}))
        self.assertEqual(r["classification"], "unjoined_or_unknown_result")
        self.assertIsNone(r["total_tenders_reported"])

    def test_open_and_awarded_are_not_closed(self):
        for status, expected in (("open-nw", "competition_still_open"), ("selec-w", "winner_selected")):
            self.assertEqual(classify(row(**{"winner-selection-status": [status]}))["classification"], expected)

    def test_secondary_cpv_not_primary(self):
        self.assertEqual(classify(row(**{"main-classification-proc": "79000000"}))["main_cpv_scope"],
                         "other_main_cpv")

    def test_lot_relaunch_requires_matching_declared_lot(self):
        r = classify(row(**{"identifier-lot": ["LOT-0001"], "procurement-relaunch": ["true"]}))
        self.assertFalse(r["single_declared_lot_relaunch_reported_true"])

    def test_wrong_window_rejected(self):
        with self.assertRaises(ValueError):
            classify(row(**{"publication-date": "2026-11-01+01:00"}))

    def test_query_complete_all_versions_and_public_projection(self):
        def fetch(body):
            self.assertEqual(body["query"], QUERY)
            self.assertFalse(body["onlyLatestVersions"])
            return {"notices": [row()], "totalNoticeCount": 1}
        result = run(fetch)
        self.assertEqual(result["primary_it_zero_tender_notice_ids"], ["729884-2026"])
        self.assertEqual(result["primary_it_notice_count"], 1)
        self.assertNotIn("buyer-name", result["public_projection_rows"][0])
        self.assertNotIn("notice-title", result["public_projection_rows"][0])
        self.assertIsNone(result["verified_paying_customers"])

    def test_incomplete_query_rejected(self):
        with self.assertRaises(ValueError):
            run(lambda body: {"notices": [row()], "totalNoticeCount": 2})

    def test_uniform_multilot_notice_without_joining_counts(self):
        r = row(**{"result-lot-identifier": ["LOT-0000", "LOT-0001"],
                   "winner-selection-status": ["clos-nw", "clos-nw"],
                   "non-award-justification": ["all-rej", "all-rej"]})
        self.assertEqual(_uniform_status(r), "clos-nw")
        self.assertEqual(_uniform_closed_reason(r), "all-rej")
        self.assertIsNone(classify(r)["total_tenders_reported"])
        r["winner-selection-status"] = ["clos-nw", "selec-w"]
        self.assertEqual(_uniform_status(r), "mixed")
        self.assertIsNone(_uniform_closed_reason(r))

    def test_frozen_real_projection_replay(self):
        path = Path("data/evidence/ted_se_it_october_nonaward_2026-11-11.json")
        result = replay(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(result["notice_count"], 111)
        self.assertEqual(result["primary_it_notice_count"], 80)
        self.assertEqual(result["primary_it_notice_level_status_counts"], {"selec-w": 66, "clos-nw": 14})
        self.assertEqual(result["primary_it_uniform_closed_reason_counts"],
                         {"all-rej": 7, "one-admis": 3, "other": 2, "no-rece": 1, "chan-need": 1})
        self.assertEqual(result["primary_it_zero_tender_notice_ids"], [])

    def test_followup_requires_complete_identity_bound_history(self):
        prior1 = row(**{"publication-number": "700958-2026"})
        prior2 = row(**{"publication-number": "694643-2026"})
        prior3 = row()
        new1 = row(**{"publication-number": "749334-2026", "form-type": "competition",
                      "notice-type": "cn-standard", "publication-date": "2026-10-29+01:00",
                      "procedure-identifier": "5b2c84f0-417b-4856-910a-5b0f874b91b5"})
        new2 = row(**{"publication-number": "778905-2026", "form-type": "competition",
                      "notice-type": "cn-standard", "publication-date": "2026-11-09+01:00",
                      "procedure-identifier": "c1aaf28e-81e7-43e0-989e-078b2ad36272"})
        def fetch(body):
            self.assertFalse(body["onlyLatestVersions"])
            rows = [prior1, prior2, prior3, new1, new2] if body["query"].startswith("publication-number") else [new1, new2]
            return {"notices": rows, "totalNoticeCount": len(rows)}
        result = followup(fetch)
        self.assertEqual(len(result["pairs"]), 2)
        self.assertTrue(result["pairs"][0]["same_buyer_label"])
        self.assertIsNone(result["pairs"][0]["legal_relaunch_link_verified"])
        self.assertNotIn("buyer-name", result["public_exact_id_rows"][0])
        def missing(body):
            if body["query"].startswith("procedure-identifier"):
                return {"notices": [new1], "totalNoticeCount": 1}
            return fetch(body)
        with self.assertRaises(ValueError):
            followup(missing)


if __name__ == "__main__":
    unittest.main()
