import unittest
from src.collect_mcp_registry import collect, collect_snapshot

class CollectorTests(unittest.TestCase):
    def test_dedup_and_cursor(self):
        cursors = []
        def fake(cursor):
            cursors.append(cursor)
            if cursor is None:
                return {"servers": [{"server": {"name": "alpha", "version": "1"}}], "metadata": {"nextCursor": "next"}}
            return {"servers": [{"server": {"name": "alpha", "version": "1"}}, {"server": {"name": "beta", "version": "1"}}], "metadata": {}}
        self.assertEqual(len(collect(5, fetch=fake)), 2)
        self.assertEqual(cursors, [None, "next"])

    def test_missing_or_invalid_name_fails_closed(self):
        for name in (None, "", " ", 5, [], {}):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "missing name"):
                collect_snapshot(1, fetch=lambda _: {
                    "servers": [{"server": {"name": name, "version": "1"}}],
                    "metadata": {"count": 1},
                })

    def test_missing_or_invalid_version_fails_closed(self):
        for version in (None, "", " ", 5, [], {}):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "missing version"):
                collect_snapshot(1, fetch=lambda _: {
                    "servers": [{"server": {"name": "org/srv", "version": version}}],
                    "metadata": {"count": 1},
                })

    def test_malformed_later_page_cannot_produce_complete_snapshot(self):
        def fake(cursor):
            if cursor is None:
                return {"servers": [{"server": {"name": "org/a", "version": "1"}}],
                        "metadata": {"count": 1, "nextCursor": "page-2"}}
            return {"servers": [{"server": {"name": "org/b"}}], "metadata": {"count": 1}}
        with self.assertRaisesRegex(ValueError, "missing version"):
            collect_snapshot(2, fetch=fake, pause=lambda _: None)

    def test_missing_metadata_fails_closed(self):
        for page in (
            {"servers": [{"server": {"name": "vendor/api", "version": "1"}}]},
            {"servers": [], "metadata": None},
            {"servers": [], "metadata": []},
        ):
            with self.subTest(page=page), self.assertRaisesRegex(ValueError, "pagination metadata"):
                collect_snapshot(1, fetch=lambda _: page)

    def test_explicit_empty_metadata_is_terminal(self):
        pages, rows, pagination = collect_snapshot(1, fetch=lambda _: {"servers": [], "metadata": {}})
        self.assertEqual((pages, rows), ([{"servers": [], "metadata": {}}], []))
        self.assertEqual(pagination, {"complete": True, "next_cursor": None, "pages_fetched": 1})

    def test_capped_cursor_never_claims_full_registry(self):
        _, rows, pagination = collect_snapshot(1, fetch=lambda _: {"servers": [{"server": {"name": "a/x", "version": "1"}}], "metadata": {"nextCursor": "cursor-2"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual(pagination, {"complete": False, "next_cursor": "cursor-2", "pages_fetched": 1})

    def test_page_count_mismatch_fails_closed(self):
        for count in (0, 2, -1, True, 1.0, "1", None):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "page count"):
                collect_snapshot(1, fetch=lambda _: {
                    "servers": [{"server": {"name": "a/x", "version": "1"}}],
                    "metadata": {"count": count},
                })

    def test_valid_count_and_optional_count(self):
        for metadata in ({"count": 1}, {}):
            _, rows, status = collect_snapshot(1, fetch=lambda _: {
                "servers": [{"server": {"name": "a/x", "version": "1"}}],
                "metadata": metadata,
            })
            self.assertEqual(len(rows), 1)
            self.assertTrue(status["complete"])

    def test_count_checks_raw_page_not_deduplicated_records(self):
        item = {"server": {"name": "a/x", "version": "1"}}
        _, rows, status = collect_snapshot(1, fetch=lambda _: {
            "servers": [item, item], "metadata": {"count": 2},
        })
        self.assertEqual(len(rows), 1)
        self.assertTrue(status["complete"])

    def test_crawl_can_reach_490_pages_with_polite_pacing(self):
        delays = []
        def fake(cursor):
            index = 0 if cursor is None else int(cursor)
            return {"servers": [{"server": {"name": f"org/server{index}", "version": "1"}}],
                    "metadata": {"count": 1, "nextCursor": str(index+1) if index < 489 else None}}
        pages, rows, status = collect_snapshot(600, fetch=fake, pause=delays.append)
        self.assertEqual((len(pages), len(rows), status["pages_fetched"]), (490, 490, 490))
        self.assertTrue(status["complete"])
        self.assertEqual(delays, [0.25]*489)

    def test_crawl_hard_limit_and_invalid_delay(self):
        for count in (0, 1001, True, 1.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                collect_snapshot(count, fetch=lambda _: {"servers": [], "metadata": {}})
        for delay in (True, -1, float('nan'), float('inf'), '0.25', 11):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                collect_snapshot(1, fetch=lambda _: {"servers": [], "metadata": {}}, page_delay_seconds=delay)


class FetchRetryTests(unittest.TestCase):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, count):
            return b'{"servers":[],"metadata":{}}'

    def test_429_and_503_recover_with_backoff_and_same_cursor(self):
        from urllib.error import HTTPError
        from src.collect_mcp_registry import fetch_page
        urls, delays = [], []
        def opener(req, timeout):
            urls.append(req.full_url)
            if len(urls) == 1:
                raise HTTPError(req.full_url, 429, 'rate limit', {'Retry-After': '2'}, None)
            if len(urls) == 2:
                raise HTTPError(req.full_url, 503, 'unavailable', {}, None)
            return self.Response()
        self.assertEqual(fetch_page('abc', opener=opener, pause=delays.append),
                         {'servers': [], 'metadata': {}})
        self.assertEqual(delays, [2, 2])
        self.assertEqual(len(set(urls)), 1)
        self.assertIn('cursor=abc', urls[0])

    def test_transient_exhaustion_stops_after_three_attempts(self):
        from urllib.error import HTTPError
        from src.collect_mcp_registry import fetch_page
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise HTTPError(req.full_url, 503, 'down', {}, None)
        with self.assertRaises(HTTPError):
            fetch_page(opener=opener, pause=lambda _: None)
        self.assertEqual(len(calls), 3)

    def test_forbidden_does_not_retry(self):
        from urllib.error import HTTPError
        from src.collect_mcp_registry import fetch_page
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise HTTPError(req.full_url, 403, 'forbidden', {}, None)
        with self.assertRaises(HTTPError):
            fetch_page(opener=opener, pause=lambda _: None)
        self.assertEqual(len(calls), 1)

    def test_long_retry_after_does_not_retry_early(self):
        from urllib.error import HTTPError
        from src.collect_mcp_registry import fetch_page
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise HTTPError(req.full_url, 429, 'rate limit', {'Retry-After': '120'}, None)
        with self.assertRaises(HTTPError):
            fetch_page(opener=opener, pause=lambda _: self.fail('must not sleep'))
        self.assertEqual(len(calls), 1)

    def test_invalid_page_arguments_rejected(self):
        from src.collect_mcp_registry import fetch_page
        for limit in (0, 101, True, '100'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                fetch_page(limit=limit, opener=lambda *a, **k: self.Response())
        for cursor in ('', [], 42):
            with self.subTest(cursor=cursor), self.assertRaises(ValueError):
                fetch_page(cursor=cursor, opener=lambda *a, **k: self.Response())

    def test_response_byte_limit_preserved(self):
        from src.collect_mcp_registry import fetch_page
        class Big(self.Response):
            def read(self, count):
                return b'0' * count
        with self.assertRaisesRegex(ValueError, 'maximum size'):
            fetch_page(opener=lambda *a, **k: Big())

if __name__ == "__main__":
    unittest.main()
