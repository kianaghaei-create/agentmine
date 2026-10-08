import unittest
from src.collect_mcp_registry import collect

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
        self.assertEqual(collect(1, fetch=lambda _: {"servers": [{"server": {"version": "1"}}]}), [])

if __name__ == "__main__":
    unittest.main()
