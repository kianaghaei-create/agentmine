"""Dated publisher evidence: concentration is not customer demand or revenue."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from src.flow_concentration_bounds import bound_effective_services
from src.x402_fee_pool import analyze

ROOT = Path(__file__).resolve().parents[1] / "data/evidence"
LATEST = ROOT / "x402_list_stats_2026-10-24T015948Z.json"
PREVIOUS = ROOT / "x402_list_stats_2026-10-23T134742Z.json"


class October24ConcentrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.latest = json.loads(LATEST.read_text(encoding="utf-8"))
        cls.previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))

    def test_provenance_and_observation_window(self):
        self.assertEqual(self.latest["source"], "https://x402-list.com/api/v1/stats")
        self.assertEqual(self.latest["license"], "CC-BY-4.0")
        self.assertEqual(self.latest["source_computed_at"], "2026-10-24T01:59:48.103Z")
        self.assertEqual(self.latest["traction_as_of"], "2026-10-24T01:41:51.477Z")

    def test_supply_not_paying_customers(self):
        self.assertEqual(self.latest["supply"]["listed_services"], 1009)
        self.assertEqual(self.latest["supply"]["services_with_traction_measurement"], 768)
        self.assertEqual(self.latest["supply"]["verified_delivery_services"], 13)
        self.assertIn("not_verified_paying_customers", self.latest["evidence_type"])

    def test_top_service_and_one_address_dominate_publisher_slice(self):
        a = self.latest["activity_30d"]
        self.assertIs(a["top_1_service_data_imported"], True)
        top1 = Decimal(str(a["top_1_service_volume_share_pct"]))
        top_buyer = Decimal(str(a["top_1_service_top_buyer_share_pct"]))
        # Conditional multiplication of two rounded publisher shares, not an
        # independently verified unique-buyer or organic-demand measurement.
        implied_pct = top1 * top_buyer / Decimal(100)
        self.assertGreater(implied_pct, Decimal(70))
        self.assertLess(implied_pct, Decimal(71))

    def test_concentration_bound_on_listed_service_flow(self):
        a = self.latest["activity_30d"]
        result = bound_effective_services(
            listed_services=self.latest["supply"]["listed_services"],
            top1_pct=str(a["top_1_service_volume_share_pct"]),
            top10_pct=str(a["top_10_services_volume_share_pct"]))
        self.assertLess(Decimal(result["effective_service_count_upper_bound"]),
                        Decimal("1.94"))
        self.assertGreater(Decimal(result["effective_service_count_upper_bound"]),
                           Decimal("1.93"))

    def test_fee_tail_scenario_not_revenue(self):
        result = analyze(self.latest, take_rate_pct="5", capture_pct="5")
        self.assertEqual(result["non_top10_observed_30d_flow_usd"], "14321.59")
        self.assertEqual(result["hypothetical_30d_fee_usd"], "35.80")
        self.assertIsNone(result["verified_agentmine_revenue_usd"])
        self.assertIsNone(result["verified_distinct_paying_customers"])

    def test_rolling_snapshot_change_not_sales_growth(self):
        old = self.previous["activity_30d"]
        new = self.latest["activity_30d"]
        self.assertGreater(new["top_1_service_volume_share_pct"],
                           old["top_1_service_volume_share_pct"])
        self.assertLess(new["listed_service_deduplicated_settlements_usd"],
                        old["listed_service_deduplicated_settlements_usd"])
        self.assertIn("Overlapping rolling 30-day windows", self.latest["caveats"][3])


if __name__ == "__main__":
    unittest.main()
