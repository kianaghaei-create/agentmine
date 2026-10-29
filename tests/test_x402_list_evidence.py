import copy
import unittest
from src.x402_list_evidence import summarize


def fixture():
    return {"data": {"computed_at": "2026-10-14T16:40:47Z", "total_services": 1028,
            "total_endpoints": 7722, "payment_ready_count": 967, "verified_count": 13,
            "traction": {"as_of": "2026-10-14T15:52:41Z", "measured_services": 772,
                         "unique_buyers_30d": 9916, "settlement_count_30d": 1695330,
                         "volume_usd_30d": 428620.984975, "top_10_services_share_pct": 96.9,
                         "top_1_service_share_pct": 63.5, "top_1_service_imported": True}},
            "provenance": {"license": "CC-BY-4.0", "cite_as": "https://x402-list.com/api/v1/stats"}}


class X402ListEvidenceTests(unittest.TestCase):
    FETCHED = "2026-10-14T17:39:00Z"

    def parse(self, value):
        return summarize(value, fetched_at=self.FETCHED)

    def test_real_shape_and_residual_fee_math(self):
        result = self.parse(fixture())
        self.assertEqual(result["flow_outside_top10_usd_30d"], "13287.25")
        self.assertEqual(result["hypothetical_1pct_fee_on_all_outside_top10_usd_30d"], "132.87")
        self.assertIsNone(result["verified_paying_customers"])
        self.assertIsNone(result["verified_agentmine_revenue_usd"])
        self.assertTrue(result["top1_data_imported"])

    def test_rejects_unattributed_data(self):
        value = fixture()
        value["provenance"]["cite_as"] = "https://other.example"
        with self.assertRaises(ValueError): self.parse(value)

    def test_rejects_future_source_timestamp(self):
        value = fixture()
        value["data"]["computed_at"] = "2026-10-15T00:00:00Z"
        with self.assertRaises(ValueError): self.parse(value)

    def test_rejects_future_fetch_timestamp_even_if_source_is_older(self):
        # Regression: a fabricated future replay timestamp must not imply freshness.
        with self.assertRaisesRegex(ValueError, "fetched_at cannot be in the future"):
            summarize(fixture(), fetched_at="2999-01-01T00:00:00Z")

    def test_rejects_naive_fetch_timestamp(self):
        with self.assertRaises(ValueError): summarize(fixture(), fetched_at="2026-10-14T17:39:00")

    def test_rejects_bool_counts(self):
        value = fixture()
        value["data"]["payment_ready_count"] = True
        with self.assertRaises(ValueError): self.parse(value)

    def test_rejects_subcounts_exceeding_total(self):
        value = fixture()
        value["data"]["verified_count"] = 9999
        with self.assertRaises(ValueError): self.parse(value)

    def test_rejects_invalid_concentration(self):
        for a, b in ((110, 110), (80, 70), (-1, 70)):
            value = fixture()
            value["data"]["traction"]["top_1_service_share_pct"] = a
            value["data"]["traction"]["top_10_services_share_pct"] = b
            with self.subTest(a=a, b=b), self.assertRaises(ValueError): self.parse(value)

    def test_rejects_nan_and_boolean_volume(self):
        for invalid in ("NaN", True, -1):
            value = fixture()
            value["data"]["traction"]["volume_usd_30d"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): self.parse(value)

    def test_rejects_false_import_flag_type(self):
        value = fixture()
        value["data"]["traction"]["top_1_service_imported"] = "false"
        with self.assertRaises(ValueError): self.parse(value)

    def test_rejects_missing_traction(self):
        value = fixture()
        value["data"].pop("traction")
        with self.assertRaises(ValueError): self.parse(value)

    def test_rejects_zero_settlements_with_volume(self):
        value = fixture()
        value["data"]["traction"]["settlement_count_30d"] = 0
        with self.assertRaises(ValueError): self.parse(value)

    def test_publisher_top_buyer_concentration_and_freshness(self):
        value = fixture()
        t = value["data"]["traction"]
        t["top_1_service_top_buyer_share_pct"] = 98.8
        t["coverage_of_measured_flow_pct"] = 18.1
        t["measured_flow_freshness"] = {
            "stale_sync_groups": 0, "total_sync_groups": 51,
            "oldest_cursor_age_seconds": 580,
        }
        result = self.parse(value)
        self.assertEqual(result["publisher_top1_service_top_buyer_share_pct"], "98.8")
        self.assertEqual(result["publisher_implied_top1_buyer_share_of_listed_flow_pct"], "62.74")
        self.assertEqual(result["publisher_measured_flow_coverage_pct"], "18.1")
        self.assertEqual(result["publisher_ingest_freshness_at_computation"], "NO_REPORTED_STALE_GROUPS")
        self.assertEqual(result["publisher_oldest_cursor_age_seconds_at_computation"], 580)
        self.assertIsNone(result["verified_paying_customers"])

    def test_unknown_freshness_is_not_reported_as_fresh(self):
        result = self.parse(fixture())
        self.assertEqual(result["publisher_ingest_freshness_at_computation"], "UNKNOWN")
        self.assertIsNone(result["publisher_implied_top1_buyer_share_of_listed_flow_pct"])

    def test_rejects_invalid_top_buyer_share_and_coverage(self):
        for key in ("top_1_service_top_buyer_share_pct", "coverage_of_measured_flow_pct"):
            for invalid in (True, -1, 101, "NaN"):
                value = fixture()
                value["data"]["traction"][key] = invalid
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    self.parse(value)

    def test_rejects_invalid_freshness_counters(self):
        for freshness in (
            {"stale_sync_groups": 3, "total_sync_groups": 2, "oldest_cursor_age_seconds": 1},
            {"stale_sync_groups": True, "total_sync_groups": 51, "oldest_cursor_age_seconds": 1},
            {"stale_sync_groups": 0, "total_sync_groups": 51, "oldest_cursor_age_seconds": -1},
            {"stale_sync_groups": 0, "total_sync_groups": 51},
            "fresh",
        ):
            value = fixture()
            value["data"]["traction"]["measured_flow_freshness"] = freshness
            with self.subTest(freshness=freshness), self.assertRaises(ValueError):
                self.parse(value)

    def test_rejects_zero_flow_with_nonzero_concentration(self):
        for field in ("top_1_service_share_pct", "top_10_services_share_pct",
                      "top_1_service_top_buyer_share_pct"):
            value = fixture()
            t = value["data"]["traction"]
            t["volume_usd_30d"] = "0"
            t["top_1_service_share_pct"] = 0
            t["top_10_services_share_pct"] = 0
            t[field] = 50
            if field == "top_1_service_share_pct":
                t["top_10_services_share_pct"] = 50
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "zero observed volume"):
                self.parse(value)

    def test_rejects_positive_flow_without_measured_services_or_leading_share(self):
        for field in ("measured_services", "top_1_service_share_pct",
                      "top_10_services_share_pct", "top_1_service_top_buyer_share_pct"):
            value = fixture()
            t = value["data"]["traction"]
            if field == "top_10_services_share_pct":
                t["top_1_service_share_pct"] = 0
            t[field] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.parse(value)

    def test_zero_volume_zero_shares_remains_valid(self):
        value = fixture()
        t = value["data"]["traction"]
        t["volume_usd_30d"] = "0"
        t["top_1_service_share_pct"] = 0
        t["top_10_services_share_pct"] = 0
        result = self.parse(value)
        self.assertEqual(result["flow_outside_top10_usd_30d"], "0.00")
        self.assertIsNone(result["verified_paying_customers"])

    def test_input_not_mutated(self):
        value = fixture()
        original = copy.deepcopy(value)
        self.parse(value)
        self.assertEqual(value, original)


if __name__ == "__main__": unittest.main()
