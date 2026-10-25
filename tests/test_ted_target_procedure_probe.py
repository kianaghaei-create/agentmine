"""Offline targeted TED procedure tests: no HTTP, no raw IDs in outputs."""
import unittest
from src.ted_cross_month_procedure import CROSS_MONTH_QUERY
from src.ted_target_procedure_probe import _query, _summarize, _target, probe
from src.ted_notice_evidence import ENDPOINT

P1 = "11111111-1111-4111-8111-111111111111"
P2 = "22222222-2222-4222-8222-222222222222"
P3 = "33333333-3333-4333-8333-333333333333"
FIELDS = ["publication-number", "publication-date", "notice-type", "notice-title",
          "buyer-name", "buyer-country", "classification-cpv", "procedure-identifier"]


def notice(n, proc, month="2026-09", cpv="72310000", kind="cn-standard"):
    return {"publication-number": n, "publication-date": month + "-12",
            "buyer-country": "SWE", "classification-cpv": [cpv],
            "procedure-identifier": proc, "notice-type": kind}


def snap(rows, query):
    return {"source_url": ENDPOINT, "query": query, "scope": "ALL",
            "complete": True, "reported_total_notices": len(rows),
            "unique_notices_collected": len(rows), "notices": rows}


class TargetedProcedureTests(unittest.TestCase):
    def setUp(self):
        self.matched = notice("000001-2026", P1)
        self.linked = notice("000002-2026", P1)
        self.unresolved = notice("000003-2026", P2)
        self.ext = snap([self.matched, self.linked, self.unresolved], CROSS_MONTH_QUERY)

    def test_target_is_selected_from_validated_cohort(self):
        n, p = _target([self.matched, self.linked, self.unresolved],
                       {"000001-2026"}, [self.linked, self.unresolved], self.ext)
        self.assertEqual(n, "000003-2026")
        self.assertEqual(p, P2)

    def test_query_is_exact_and_bounded(self):
        self.assertEqual(_query(P2),
                         'procedure-identifier = "' + P2 + '" AND publication-date >= 20260101 AND publication-date <= 20261025')
        for bad in ('abc" OR buyer-country = SWE', "123", None):
            with self.assertRaises(ValueError):
                _query(bad)

    def test_realistic_cross_cpv_peer_not_misreported_as_lead(self):
        extra = notice("000004-2026", P2, "2026-04", "72220000")
        report = _summarize("000003-2026", P2,
                            snap([self.unresolved, extra], _query(P2)))
        self.assertEqual(report["notices_in_procedure"], 2)
        self.assertEqual(report["peer_cpv_categories"], {"outside_7231_cpv": 1})
        self.assertEqual(report["peer_publication_months"], {"2026-04": 1})
        self.assertIsNone(report["verified_new_distinct_procurement"])
        self.assertIsNone(report["verified_incumbent_search_miss"])
        for secret in (P2, "000003-2026", "000004-2026"):
            self.assertNotIn(secret, str(report))

    def test_no_peers_is_unknown_not_new_opportunity(self):
        report = _summarize("000003-2026", P2,
                            snap([self.unresolved], _query(P2)))
        self.assertEqual(report["peer_notices"], 0)
        self.assertIsNone(report["verified_new_distinct_procurement"])

    def test_fail_closed_incomplete_or_wrong_query_or_missing_target(self):
        for field, bad in (("complete", False), ("query", "different"),
                           ("reported_total_notices", 99)):
            x = snap([self.unresolved], _query(P2)); x[field] = bad
            with self.assertRaises(ValueError):
                _summarize("000003-2026", P2, x)
        with self.assertRaisesRegex(ValueError, "did not return"):
            _summarize("000003-2026", P2,
                       snap([notice("000004-2026", P2)], _query(P2)))

    def test_fail_closed_mismatched_uuid_date_duplicate_and_cpv(self):
        for bad in (notice("000004-2026", P3),
                    notice("000004-2026", P2, "2025-12"),
                    dict(notice("000004-2026", P2), **{"classification-cpv": ["BAD"]})):
            with self.assertRaises(ValueError):
                _summarize("000003-2026", P2,
                           snap([self.unresolved, bad], _query(P2)))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _summarize("000003-2026", P2,
                       snap([self.unresolved, self.unresolved], _query(P2)))

    def test_missing_cpv_is_unknown(self):
        peer = notice("000004-2026", P2); peer.pop("classification-cpv")
        report = _summarize("000003-2026", P2,
                            snap([self.unresolved, peer], _query(P2)))
        self.assertEqual(report["peer_cpv_categories"], {"missing_cpv_unknown": 1})

    def test_probe_uses_injected_read_only_fetcher_and_aggregates(self):
        peer = notice("000004-2026", P2, "2026-03", "72220000")
        def fetch(body):
            self.assertEqual(body["query"], _query(P2))
            self.assertIn("procedure-identifier", body["fields"])
            return {"timedOut": False, "notices": [self.unresolved, peer],
                    "totalNoticeCount": 2, "iterationNextToken": "terminal"}
        report = probe([self.matched, self.linked, self.unresolved],
                       {"000001-2026"}, [self.linked, self.unresolved],
                       self.ext, fetch_page=fetch, fields=FIELDS)
        self.assertEqual(report["peer_cpv_categories"], {"outside_7231_cpv": 1})
        self.assertNotIn(P2, str(report))

    def test_ambiguous_unresolved_count_fails_closed(self):
        another = notice("000005-2026", P3)
        ext = snap(self.ext["notices"] + [another], CROSS_MONTH_QUERY)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            _target(self.ext["notices"] + [another], {"000001-2026"},
                    [self.linked, self.unresolved, another], ext)


if __name__ == "__main__":
    unittest.main()
