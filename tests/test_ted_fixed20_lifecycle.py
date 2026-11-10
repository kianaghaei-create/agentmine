import unittest
from src.ted_fixed20_lifecycle import review, PROJECTION

P = "ba03174a-dfe0-4dd2-8812-34d3e4a2df2f"
Q = "8ed8a7d2-ee71-40ce-9267-6475a5e43c95"
IDS = [f"{600201+i}-2026" for i in range(20)]


def cohort():
    return {"complete_frame_reconciled": True, "cohort_size": 20,
            "notice_items": [{"publication_number": number} for number in IDS]}


def row(number, procedure=P, **fields):
    return {"publication-number": number, "procedure-identifier": procedure, **fields}


def response(rows, total=None):
    return {"notices": rows, "totalNoticeCount": len(rows) if total is None else total, "timedOut": False}


class Tests(unittest.TestCase):
    def test_all_versions_and_lifecycle(self):
        calls = []
        originals = [row(n) for n in IDS]
        award = row("742670-2026", **{"form-type": "result", "framework-value-notice": 6000000,
                                      "framework-approximate-value-notice": 4000000,
                                      "received-submissions-type-code": ["tenders"],
                                      "received-submissions-type-val": [1]})
        change = row("700000-2026", **{"change-notice-version-identifier": "old-01"})
        def fetch(body):
            calls.append(body)
            return response(originals if len(calls) == 1 else originals+[award, change])
        result = review(cohort(), fetch_page=fetch)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c["onlyLatestVersions"] is False for c in calls))
        self.assertEqual(calls[0]["fields"], PROJECTION)
        self.assertEqual(result["frozen_ids_with_metadata"], 20)
        self.assertEqual(result["distinct_procedure_ids"], 1)
        self.assertEqual(result["procedures_with_result_metadata"], 1)
        self.assertEqual(result["procedures_with_change_reference_metadata"], 1)
        self.assertEqual(result["new_original_xml_pdf_reviews"], 0)
        self.assertEqual(result["amendment_histories_cleared"], 0)
        self.assertIsNone(result["verified_supplier_payments"])
        self.assertEqual(result["procedure_query"]["notices"][-2]["framework-approximate-value-notice"], 4000000)

    def test_missing_ids_and_unbound_procedure_are_explicit(self):
        calls = []
        def fetch(body):
            calls.append(body)
            return response([row(IDS[0], "not-a-uuid")])
        result = review(cohort(), fetch_page=fetch)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result["missing_frozen_ids"]), 19)
        self.assertEqual(len(result["frozen_ids_without_procedure"]), 20)
        self.assertIsNone(result["procedure_query"])

    def test_outside_frozen_cohort_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside frozen"):
            review(cohort(), fetch_page=lambda _: response([row("999999-2026")]))

    def test_outside_procedure_rejected(self):
        calls = iter([response([row(IDS[0])]), response([row("999999-2026", Q)])])
        with self.assertRaisesRegex(ValueError, "not bound"):
            review(cohort(), fetch_page=lambda _: next(calls))

    def test_incomplete_query_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete TED query"):
            review(cohort(), fetch_page=lambda _: response([row(IDS[0])], total=2))

    def test_canonical_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate canonical"):
            review(cohort(), fetch_page=lambda _: response([row(IDS[0]), row("0"+IDS[0])]))

    def test_publication_number_padding_and_no_contact_copy(self):
        raw = row("0"+IDS[0], **{"winner-email": "not-exported@example.invalid"})
        calls = iter([response([raw]), response([raw])])
        result = review(cohort(), fetch_page=lambda _: next(calls))
        self.assertEqual(result["original_id_query"]["notices"][0]["publication-number"], IDS[0])
        self.assertNotIn("winner-email", result["original_id_query"]["notices"][0])

    def test_cohort_denominator_cannot_change(self):
        bad = cohort(); bad["notice_items"].pop()
        with self.assertRaisesRegex(ValueError, "frozen reconciled"):
            review(bad, fetch_page=lambda _: self.fail("must not query"))


if __name__ == "__main__":
    unittest.main()
