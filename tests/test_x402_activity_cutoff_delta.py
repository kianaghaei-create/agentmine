"""Regression tests for x402 publisher recomputation versus actual activity cutoff."""
import copy
import json
from pathlib import Path
import unittest
from src.x402_activity_cutoff_delta import analyze


EVIDENCE = (Path(__file__).resolve().parents[1] / "data/evidence"
            / "x402_list_unchanged_activity_cutoff_2026-10-29.json")


def fixture():
    return {
        "evidence_type": "publisher_rolling_snapshot_comparison_not_paid_demand",
        "source_url": "https://x402-list.com/api/v1/stats",
        "license": "CC-BY-4.0",
        "baseline": {
            "computed_at_utc": "2026-10-28T20:45:55.940Z",
            "activity_as_of_utc": "2026-10-28T11:42:52.410Z",
            "listed_services": 1187, "listed_endpoints": 8778,
            "delivery_verified_services": 13,
            "rolling_30d_flow_usd": "328371.419277",
        },
        "latest": {
            "computed_at_utc": "2026-10-29T18:46:31.865Z",
            "activity_as_of_utc": "2026-10-28T11:42:52.410Z",
            "listed_services": 1207, "listed_endpoints": 9015,
            "delivery_verified_services": 13,
            "rolling_30d_flow_usd": "326115.826195",
        },
    }


class X402ActivityCutoffDeltaTests(unittest.TestCase):
    def test_same_activity_cutoff_not_new_demand(self):
        result = analyze(fixture())
        self.assertFalse(result["activity_cutoff_advanced"])
        self.assertEqual(result["fresh_activity_evidence_status"],
                         "UNCHANGED_PUBLISHER_ACTIVITY_CUTOFF")
        self.assertEqual(result["publisher_listings_delta"], 20)
        self.assertEqual(result["publisher_endpoints_delta"], 237)
        self.assertEqual(result["publisher_delivery_verified_services_delta"], 0)
        self.assertEqual(result["publisher_rolling_30d_flow_delta_usd"], "-2255.593082")
        self.assertFalse(result["flow_delta_proves_new_settlement_activity"])
        self.assertIsNone(result["verified_agentmine_revenue_usd"])

    def test_real_dated_evidence_matches_prior_committed_snapshot(self):
        actual = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        previous = json.loads((EVIDENCE.parent / "x402_list_stats_2026-10-28T204555Z.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(actual["baseline"]["computed_at_utc"],
                         previous["source_computed_at_utc"])
        self.assertEqual(actual["baseline"]["activity_as_of_utc"],
                         previous["activity_as_of_utc"])
        self.assertEqual(actual["baseline"]["listed_services"],
                         previous["current"]["listed_services"])
        self.assertEqual(actual["baseline"]["listed_endpoints"],
                         previous["current"]["listed_endpoints"])
        self.assertEqual(actual["baseline"]["rolling_30d_flow_usd"],
                         str(previous["current"]["listed_service_deduplicated_settlement_usd_30d"]))
        self.assertEqual(analyze(actual)["fresh_activity_evidence_status"],
                         "UNCHANGED_PUBLISHER_ACTIVITY_CUTOFF")

    def test_advanced_activity_cutoff_still_not_verified_sales(self):
        data = fixture()
        data["latest"]["activity_as_of_utc"] = "2026-10-29T12:00:00Z"
        result = analyze(data)
        self.assertTrue(result["activity_cutoff_advanced"])
        self.assertFalse(result["flow_delta_proves_new_settlement_activity"])
        self.assertIn("NOT_INDEPENDENTLY_VERIFIED", result["fresh_activity_evidence_status"])

    def test_regressed_cutoff_rejected(self):
        data = fixture()
        data["latest"]["activity_as_of_utc"] = "2026-10-27T12:00:00Z"
        with self.assertRaisesRegex(ValueError, "regressed"):
            analyze(data)

    def test_reversed_computation_order_rejected(self):
        data = fixture()
        data["latest"]["computed_at_utc"] = "2026-10-27T12:00:00Z"
        with self.assertRaises(ValueError):
            analyze(data)

    def test_future_or_naive_timestamps_rejected(self):
        for value in ("2999-01-01T00:00:00Z", "2026-10-29T18:46:31"):
            with self.subTest(value=value):
                data = fixture()
                data["latest"]["computed_at_utc"] = value
                with self.assertRaises(ValueError):
                    analyze(data)

    def test_malformed_flow_and_counts_rejected(self):
        for field, value in (("rolling_30d_flow_usd", "-1"),
                             ("rolling_30d_flow_usd", "NaN"),
                             ("rolling_30d_flow_usd", 3.5),
                             ("listed_services", True),
                             ("listed_services", -1),
                             ("delivery_verified_services", 5000)):
            with self.subTest(field=field, value=value):
                data = fixture()
                data["latest"][field] = value
                with self.assertRaises(ValueError):
                    analyze(data)

    def test_unlicensed_or_untrusted_publisher_rejected(self):
        for field, value in (("license", "unknown"),
                             ("source_url", "https://example.org/stats"),
                             ("evidence_type", "verified_paid_demand")):
            with self.subTest(field=field):
                data = fixture()
                data[field] = value
                with self.assertRaises(ValueError):
                    analyze(data)


if __name__ == "__main__":
    unittest.main()
