import unittest

from src.ted_nonaward_research import QUERY, classify, review, run


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


if __name__ == "__main__":
    unittest.main()
