"""Offline provenance and arithmetic regressions; no observed AgentMine demand."""
import copy
import json
from decimal import Decimal
from pathlib import Path
import unittest

from src.x402_fee_pool import analyze


FIXTURE = (Path(__file__).resolve().parents[1] /
           "data/evidence/x402_list_stats_2026-10-23T134742Z.json")


def snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FeePoolIntegrityTests(unittest.TestCase):
    def test_source_bound_fixture_produces_only_hypothetical_fee(self):
        result = analyze(snapshot(), take_rate_pct="5", capture_pct="5")
        self.assertEqual(result["snapshot_date"], "2026-10-23T13:41:53.676Z")
        self.assertEqual(Decimal(result["non_top10_observed_30d_flow_usd"]),
                         Decimal("15207.02"))
        self.assertEqual(Decimal(result["hypothetical_30d_fee_usd"]),
                         Decimal("38.02"))
        self.assertIsNone(result["verified_agentmine_revenue_usd"])
        self.assertIsNone(result["verified_distinct_paying_customers"])

    def test_rejects_missing_or_mismatched_publisher_license(self):
        for field, value in (("publisher", "unknown"), ("license", "unknown"),
                             ("source", "https://example.com/stats"),
                             ("license", None)):
            with self.subTest(field=field, value=value):
                evidence = snapshot()
                evidence[field] = value
                with self.assertRaisesRegex(ValueError, "provenance"):
                    analyze(evidence)

    def test_rejects_future_missing_naive_or_inverted_activity_times(self):
        for field, value in (("source_computed_at", "2999-01-01T00:00:00Z"),
                             ("traction_as_of", "2999-01-01T00:00:00Z"),
                             ("traction_as_of", "2026-10-23T13:41:53"),
                             ("source_computed_at", None),
                             ("traction_as_of", "invalid"),
                             ("traction_as_of", "2026-10-23T15:00:00Z")):
            with self.subTest(field=field, value=value):
                evidence = snapshot()
                evidence[field] = value
                with self.assertRaises(ValueError):
                    analyze(evidence)

    def test_rejects_positive_flow_with_zero_leading_service_share(self):
        for field in ("top_1_service_volume_share_pct",
                      "top_10_services_volume_share_pct"):
            with self.subTest(field=field):
                evidence = snapshot()
                evidence["activity_30d"][field] = 0
                with self.assertRaises(ValueError):
                    analyze(evidence)

    def test_rejects_impossible_top_ten_share_for_largest_service(self):
        # Ten services each <= 8% cannot jointly account for 95% of flow.
        for top1, top10 in ((8, 95), (1, 100), ('9.49', '95')):
            with self.subTest(top1=top1, top10=top10):
                evidence = snapshot()
                evidence['activity_30d']['top_1_service_volume_share_pct'] = top1
                evidence['activity_30d']['top_10_services_volume_share_pct'] = top10
                with self.assertRaisesRegex(ValueError, 'top-ten share inconsistent'):
                    analyze(evidence)

    def test_accepts_top_ten_equal_to_ten_times_largest_service(self):
        evidence = snapshot()
        evidence['activity_30d']['top_1_service_volume_share_pct'] = '9.5'
        evidence['activity_30d']['top_10_services_volume_share_pct'] = '95'
        result = analyze(evidence)
        self.assertEqual(result['top10_share_pct'], '95')
        self.assertIsNone(result['verified_agentmine_revenue_usd'])

    def test_rejects_zero_flow_with_positive_concentration(self):
        evidence = snapshot()
        evidence["activity_30d"]["listed_service_deduplicated_settlements_usd"] = 0
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            analyze(evidence)

    def test_zero_flow_zero_shares_still_valid_scenario(self):
        evidence = snapshot()
        activity = evidence["activity_30d"]
        activity["listed_service_deduplicated_settlements_usd"] = 0
        activity["top_1_service_volume_share_pct"] = 0
        activity["top_10_services_volume_share_pct"] = 0
        result = analyze(evidence)
        self.assertEqual(result["hypothetical_30d_fee_usd"], "0.00")


if __name__ == "__main__":
    unittest.main()
