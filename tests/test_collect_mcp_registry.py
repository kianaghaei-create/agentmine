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

    def test_missing_name_skipped(self):
        self.assertEqual(collect(1, fetch=lambda _: {"servers": [{"server": {"version": "1"}}], "metadata": {}}), [])

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

if __name__ == "__main__":
    unittest.main()
