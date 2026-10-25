import unittest
from src.ted_notice_evidence import collect, request_body, summarize


def row(identifier, buyer=None):
    return {"publication-number": identifier, "buyer-name": buyer}


class TedNoticeEvidenceTests(unittest.TestCase):
    def test_request_body_has_explicit_scope_and_pagination(self):
        result = request_body('publication-date>=20261001', limit=20)
        self.assertEqual(result['scope'], 'ALL')
        self.assertEqual(result['paginationMode'], 'ITERATION')
        self.assertTrue(result['onlyLatestVersions'])
        self.assertNotIn('iterationNextToken', result)

    def test_rejects_bad_request_parameters(self):
        for value in (True, 0, 251, 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                request_body('PD>=20261001', limit=value)
        with self.assertRaises(ValueError):
            request_body(' ')

    def test_bounded_procedure_projection_preserves_default_fields(self):
        from src.ted_notice_evidence import FIELDS
        fields = FIELDS + ["procedure-identifier", "previous-notice-id-proc"]
        body = request_body("publication-date>=20260901", fields=fields)
        self.assertEqual(body["fields"], fields)
        calls = []
        def fetch(request):
            calls.append(request)
            return {"notices": [], "totalNoticeCount": 0, "timedOut": False}
        collect("publication-date>=20260901", fetch_page=fetch, fields=fields)
        self.assertEqual(calls[0]["fields"], fields)
        for bad in ([], ["procedure-identifier"], FIELDS + ["procedure-identifier", "procedure-identifier"],
                    FIELDS + [42]):
            with self.assertRaisesRegex(ValueError, "projection"):
                request_body("publication-date>=20260901", fields=bad)

    def test_complete_two_page_iteration(self):
        calls = []
        def fetch(body):
            calls.append(body)
            if len(calls) == 1:
                return {"notices": [row('1-2026','City A')], "totalNoticeCount": 2,
                        "iterationNextToken": 'next', "timedOut": False}
            return {"notices": [row('2-2026','City B')], "totalNoticeCount": 2,
                    "iterationNextToken": None, "timedOut": False}
        snapshot = collect('PD>=20261001', fetch, max_pages=2, limit=1,
                           observed_at='2026-10-12T12:00:00Z')
        self.assertEqual(calls[1]['iterationNextToken'], 'next')
        self.assertTrue(snapshot['complete'])
        self.assertEqual(snapshot['unique_notices_collected'], 2)
        self.assertEqual(snapshot['pages_fetched'], 2)

    def test_terminal_token_does_not_mark_complete_result_partial(self):
        snapshot = collect('PD>=20261001', lambda _: {
            "notices": [row('1-2026'), row('2-2026')],
            "totalNoticeCount": 2, "iterationNextToken": 'terminal',
            "timedOut": False}, max_pages=1, limit=2)
        self.assertTrue(snapshot['complete'])
        self.assertIsNone(snapshot['next_iteration_token'])
        self.assertEqual(snapshot['unique_notices_collected'], 2)

    def test_unique_notice_count_cannot_exceed_reported_total(self):
        with self.assertRaisesRegex(ValueError, 'exceed'):
            collect('PD>=20261001', lambda _: {
                "notices": [row('1-2026'), row('2-2026')],
                "totalNoticeCount": 1, "iterationNextToken": 'n',
                "timedOut": False}, max_pages=1, limit=2)

    def test_partial_crawl_preserves_next_token(self):
        snapshot = collect('PD>=20261001', lambda _: {
            "notices": [row('1-2026')], "totalNoticeCount": 10,
            "iterationNextToken": 'next', "timedOut": False}, max_pages=1)
        self.assertFalse(snapshot['complete'])
        self.assertEqual(snapshot['next_iteration_token'], 'next')

    def test_missing_token_cannot_claim_complete(self):
        snapshot = collect('PD>=20261001', lambda _: {
            "notices": [row('1-2026')], "totalNoticeCount": 10,
            "timedOut": False}, max_pages=1)
        self.assertFalse(snapshot['complete'])
        self.assertIsNone(snapshot['next_iteration_token'])

    def test_repeated_token_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'repeated'):
            collect('PD>=20261001', lambda _: {
                "notices": [row('1-2026')], "totalNoticeCount": 10,
                "iterationNextToken": 'again', "timedOut": False}, max_pages=2)

    def test_timeout_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'timed out'):
            collect('PD>=20261001', lambda _: {
                "notices": [], "totalNoticeCount": 0, "timedOut": True})

    def test_total_change_fails_closed(self):
        n = [0]
        def fetch(_):
            n[0] += 1
            return {"notices": [row(str(n[0]))], "totalNoticeCount": n[0] + 1,
                    "iterationNextToken": 'n' if n[0] == 1 else None}
        with self.assertRaisesRegex(ValueError, 'changed'):
            collect('PD>=20261001', fetch, max_pages=2)

    def test_conflicting_duplicate_fails_closed(self):
        n = [0]
        def fetch(_):
            n[0] += 1
            return {"notices": [row('same', 'A' if n[0] == 1 else 'B')],
                    "totalNoticeCount": 2, "iterationNextToken": 'n' if n[0] == 1 else None}
        with self.assertRaisesRegex(ValueError, 'conflicting duplicate'):
            collect('PD>=20261001', fetch, max_pages=2)

    def test_identical_duplicate_does_not_inflate(self):
        n = [0]
        def fetch(_):
            n[0] += 1
            return {"notices": [row('same','A')], "totalNoticeCount": 1,
                    "iterationNextToken": 'n' if n[0] == 1 else None}
        snapshot = collect('PD>=20261001', fetch, max_pages=2)
        self.assertEqual(snapshot['unique_notices_collected'], 1)
        self.assertTrue(snapshot['complete'])

    def test_missing_publication_id_fails(self):
        with self.assertRaisesRegex(ValueError, 'publication-number'):
            collect('PD>=20261001', lambda _: {
                "notices": [{}], "totalNoticeCount": 1})

    def test_buyer_labels_are_not_verified_companies(self):
        snapshot = collect('PD>=20261001', lambda _: {
            "notices": [row('a', {'eng': ['Agency A']}), row('b', {'eng': ['Agency A']}),
                        row('c', {'swe': ['Agency B']}), row('d', None)],
            "totalNoticeCount": 4})
        stats = summarize(snapshot)
        self.assertEqual(stats['distinct_unverified_buyer_name_labels'], 2)
        self.assertEqual(stats['buyer_name_label_coverage'], 0.75)
        self.assertAlmostEqual(stats['largest_buyer_name_notice_share_in_known_sample'], 2/3)
        self.assertAlmostEqual(stats['buyer_name_hhi_in_known_sample'], 5/9)
        self.assertIsNone(stats['verified_distinct_buyers'])
        self.assertIsNone(stats['agentmine_revenue'])

    def test_summary_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            summarize({'notices': [row('same'), row('same')],
                       'complete': True, 'unique_notices_collected': 2})

    def test_rejects_unaware_observation_timestamp(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            collect('PD>=20261001', lambda _: {}, observed_at='2026-10-12T10:00:00')

    def test_no_live_network_when_injected(self):
        called = []
        def fake(body):
            called.append(body)
            return {'notices': [], 'totalNoticeCount': 0}
        result = collect('PD>=20261001', fake)
        self.assertEqual(len(called), 1)
        self.assertTrue(result['complete'])
        self.assertEqual(summarize(result)['notice_count'], 0)


if __name__ == '__main__':
    unittest.main()
