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

    def test_input_not_mutated(self):
        value = fixture()
        original = copy.deepcopy(value)
        self.parse(value)
        self.assertEqual(value, original)


if __name__ == "__main__": unittest.main()
