"""Offline, synthetic tests: cross-month TED checks never publish raw IDs."""
import unittest
from src.ted_cross_month_procedure import triage_cross_month, CROSS_MONTH_QUERY, SOURCE

P1 = "11111111-1111-4111-8111-111111111111"
P2 = "22222222-2222-4222-8222-222222222222"
P3 = "33333333-3333-4333-8333-333333333333"


def notice(number, month, proc, kind="cn-standard"):
    return {"publication-number": number, "publication-date": month + "-12",
            "buyer-country": "SWE", "classification-cpv": ["72310000"],
            "notice-type": kind, "procedure-identifier": proc}


def snapshot(rows):
    return {"source_url": SOURCE, "query": CROSS_MONTH_QUERY, "scope": "ALL",
            "complete": True, "notices": rows,
            "reported_total_notices": len(rows), "unique_notices_collected": len(rows)}


class CrossMonthProcedureTests(unittest.TestCase):
    def test_official_cross_month_links_and_unknown_are_distinct(self):
        matched = notice("000001-2026", "2026-09", P1)
        a = notice("000002-2026", "2026-09", P1)
        b = notice("000003-2026", "2026-09", P2)
        c = notice("000004-2026", "2026-09", P3)
        august = notice("000005-2026", "2026-08", P2)
        result = triage_cross_month([matched, a, b, c], {"000001-2026"},
                                    [a, b, c], snapshot([matched, a, b, c, august]))
        self.assertEqual(result["procedure_link_categories"], {
            "linked_to_matched_september_notice": 1,
            "linked_to_august_or_october_notice": 1,
            "no_link_in_bounded_7231_cohort_not_proof_of_distinct_opportunity": 1})
        self.assertEqual(result["publication_month_counts"], {"2026-08": 1, "2026-09": 4})
        self.assertIsNone(result["verified_incumbent_search_misses"])
        for secret in (P1, P2, P3, "000002-2026", "000005-2026"):
            self.assertNotIn(secret, str(result))

    def test_same_month_unmatched_award_link_is_not_new_opportunity(self):
        matched = notice("000001-2026", "2026-09", P1)
        missing = notice("000002-2026", "2026-09", P2)
        award = notice("000003-2026", "2026-09", P2, kind="can-standard")
        result = triage_cross_month([matched, missing, award], {"000001-2026"},
                                    [missing], snapshot([matched, missing, award]))
        self.assertEqual(result["procedure_link_categories"],
                         {"linked_to_other_september_notice": 1})

    def test_reject_partial_and_missing_september_cohort(self):
        a = notice("000001-2026", "2026-09", P1)
        b = notice("000002-2026", "2026-09", P2)
        snap = snapshot([a])
        with self.assertRaisesRegex(ValueError, "missing September"):
            triage_cross_month([a, b], {"000001-2026"}, [b], snap)
        snap = snapshot([a, b]); snap["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete"):
            triage_cross_month([a, b], {"000001-2026"}, [b], snap)

    def test_real_ted_date_offset_shape_is_accepted(self):
        a = notice("000001-2026", "2026-09", P1)
        b = dict(a); b["publication-date"] = "2026-09-12+02:00"
        result = triage_cross_month([b], set(), [b], snapshot([b]))
        self.assertEqual(result["september_notice_numbers_present"], 1)
        c = dict(b); c["publication-date"] = "2026-09-12+99:00"
        with self.assertRaises(ValueError):
            triage_cross_month([b], set(), [b], snapshot([c]))

    def test_reject_inconsistent_projection_and_dates(self):
        a = notice("000001-2026", "2026-09", P1)
        for field, bad in (("buyer-country", "NOR"), ("classification-cpv", ["72000000"]),
                           ("publication-date", "2026-11-12")):
            wrong = dict(a); wrong[field] = bad
            with self.assertRaises(ValueError):
                triage_cross_month([a], set(), [a], snapshot([wrong]))
        wrong = dict(a); wrong["publication-date"] = "2026-09-13"
        with self.assertRaisesRegex(ValueError, "dates disagree"):
            triage_cross_month([a], set(), [a], snapshot([wrong]))

    def test_reject_duplicate_or_wrong_unmatched_membership(self):
        a = notice("000001-2026", "2026-09", P1)
        b = notice("000002-2026", "2026-09", P2)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            triage_cross_month([a, b], set(), [b, b], snapshot([a, b]))
        with self.assertRaisesRegex(ValueError, "membership"):
            triage_cross_month([a, b], {"000001-2026"}, [a], snapshot([a, b]))

    def test_missing_uuid_remains_unknown(self):
        a = notice("000001-2026", "2026-09", None)
        result = triage_cross_month([a], set(), [a], snapshot([a]))
        self.assertEqual(result["procedure_link_categories"], {"missing_procedure_identifier": 1})


if __name__ == "__main__":
    unittest.main()
