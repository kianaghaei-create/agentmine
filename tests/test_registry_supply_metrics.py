import unittest
from src.registry_supply_metrics import analyze_snapshot


def snapshot(rows, complete=True):
    return {
        "observed_at": "2026-10-09T13:40:00+00:00",
        "source": "https://registry.modelcontextprotocol.io/v0.1/servers",
        "records": rows,
        "pagination": {
            "complete": complete,
            "pages_fetched": 1,
            "next_cursor": None if complete else "cursor",
        },
    }


def row(name, version="1"):
    return {"server": {"name": name, "version": version}}


class RegistrySupplyTests(unittest.TestCase):
    def test_distinct_names_not_versions(self):
        result = analyze_snapshot(snapshot([
            row("com.a/one", "1"), row("com.a/one", "2"), row("com.b/two"),
        ]))
        self.assertEqual(result["listing_rows"], 3)
        self.assertEqual(result["distinct_server_names"], 2)
        self.assertEqual(result["duplicate_name_rows"], 1)
        self.assertEqual(result["sample_namespace_hhi"], 0.5)
        self.assertEqual(result["complete_registry_namespace_hhi"], 0.5)

    def test_partial_does_not_claim_full_registry(self):
        result = analyze_snapshot(snapshot([row("com.a/one"), row("com.a/two")], False))
        self.assertEqual(result["sample_namespace_hhi"], 1)
        self.assertIsNone(result["complete_registry_namespace_hhi"])
        self.assertEqual(result["scope"], "partial_registry_sample_only")

    def test_unknown_namespace_is_not_monopoly(self):
        result = analyze_snapshot(snapshot([row("bad"), row("com.a/one")]))
        self.assertEqual(result["server_names_with_unknown_namespace"], 1)
        self.assertEqual(result["namespace_label_coverage"], 0.5)

    def test_empty_and_malformed(self):
        result = analyze_snapshot(snapshot([{}, "not dict", row("  ")]))
        self.assertEqual(result["invalid_name_rows"], 3)
        self.assertIsNone(result["sample_namespace_hhi"])
        self.assertIsNone(result["verified_paying_customers"])

    def test_rejects_missing_source(self):
        data = snapshot([])
        data["source"] = ""
        with self.assertRaises(ValueError):
            analyze_snapshot(data)

    def test_rejects_naive_time(self):
        data = snapshot([])
        data["observed_at"] = "2026-10-09T12:00:00"
        with self.assertRaises(ValueError):
            analyze_snapshot(data)

    def test_rejects_bad_pagination(self):
        for pagination in (
            {"complete": 1, "pages_fetched": 1},
            {"complete": False, "pages_fetched": 1},
            {"complete": True, "pages_fetched": 0},
        ):
            data = snapshot([])
            data["pagination"] = pagination
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                analyze_snapshot(data)

    def test_does_not_infer_business_or_revenue(self):
        result = analyze_snapshot(snapshot([row("com.a/one")]))
        self.assertIsNone(result["verified_supplier_businesses"])
        self.assertIsNone(result["revenue_usd"])


if __name__ == "__main__":
    unittest.main()
