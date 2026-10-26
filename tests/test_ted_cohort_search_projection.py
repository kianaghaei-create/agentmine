import unittest
from src.ted_cohort_search_projection import PROJECTION, project_cohort


def cohort():
    return {
        "complete_frame_reconciled": True,
        "cohort_size": 20,
        "query": "publication-date >= 20260901 AND buyer-country = SWE",
        "selection_rule": "fixed first 20",
        "complete_query_frame_notices": 20,
        "notice_items": [{"publication_number": f"{600201+i}-2026"} for i in range(20)],
    }


def fake_page(body):
    rows = [{"publication-number": f"{600201+i}-2026",
             "main-classification-proc": ["79411100"],
             "additional-classification-proc": ["72221000"],
             "deadline-receipt-tender-date-lot": ["2026-09-29"]}
            for i in range(20)]
    return {"notices": rows, "totalNoticeCount": 20, "timedOut": False}


class Tests(unittest.TestCase):
    def test_fixed_cohort_raw_field_preservation(self):
        result = project_cohort(cohort(), fetch_page=fake_page, observed_at="2026-10-26T10:00:00Z")
        self.assertEqual(result["projected_cohort_notice_count"], 20)
        self.assertEqual(result["missing_cohort_notice_count"], 0)
        self.assertEqual(result["field_nonempty_coverage_in_fixed_20"]["main-classification-proc"], 20)
        self.assertEqual(result["items"][0]["official_search_fields"]["main-classification-proc"], ["79411100"])
        self.assertEqual(result["items"][0]["official_search_fields"]["additional-classification-proc"], ["72221000"])
        self.assertFalse(result["items"][0]["legal_deadline_verified"])
        self.assertIsNone(result["verified_agentmine_revenue"])

    def test_only_authorized_projection_requested(self):
        calls = []
        def fetch(body):
            calls.append(body)
            return fake_page(body)
        project_cohort(cohort(), fetch_page=fetch)
        self.assertEqual(calls[0]["fields"], PROJECTION)
        self.assertEqual(calls[0]["query"], cohort()["query"])
        self.assertTrue(calls[0]["onlyLatestVersions"])

    def test_missing_selected_id_explicit_and_denominator_held(self):
        def partial(body):
            return {"notices": [{"publication-number": f"{600201+i}-2026"} for i in range(1, 20)],
                    "totalNoticeCount": 19}
        result = project_cohort(cohort(), fetch_page=partial)
        self.assertEqual(result["missing_cohort_notice_count"], 1)
        self.assertEqual(result["items"][0]["status"], "missing_from_new_official_query_frame")
        self.assertTrue(result["frame_count_changed"])

    def test_incomplete_frame_fails_closed(self):
        def partial(body):
            return {"notices": [{"publication-number": "600201-2026"}],
                    "totalNoticeCount": 40}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            project_cohort(cohort(), fetch_page=partial)

    def test_duplicate_or_partial_cohort_rejected(self):
        x = cohort()
        x["notice_items"][1] = x["notice_items"][0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            project_cohort(x, fetch_page=fake_page)
        x = cohort()
        x["notice_items"].pop()
        with self.assertRaisesRegex(ValueError, "exact 20"):
            project_cohort(x, fetch_page=fake_page)

    def test_unverified_supplier_claims_remain_null(self):
        result = project_cohort(cohort(), fetch_page=fake_page)
        self.assertIsNone(result["verified_supplier_savings"])
        self.assertIsNone(result["verified_agentmine_customers"])
        self.assertFalse(result["items"][0]["submission_portal_verified"])


if __name__ == "__main__":
    unittest.main()
