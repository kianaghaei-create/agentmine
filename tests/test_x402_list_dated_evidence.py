"""Replay selected dated publisher fields; not a raw API capture or buyer proof."""
import json
from pathlib import Path
import unittest

from src.x402_list_evidence import summarize


EVIDENCE = (Path(__file__).resolve().parents[1] / "data" / "evidence"
            / "x402_list_selected_stats_2026-10-26.json")


def publisher_payload():
    saved = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if saved["evidence_type"] != "publisher_selected_fields_not_raw_response":
        raise ValueError("expected selected source fields, not raw or audited ledger")
    fields = saved["selected_publisher_fields"]
    return {
        "data": {
            "computed_at": saved["source_computed_at_utc"],
            "total_services": fields["total_services"],
            "total_endpoints": fields["total_endpoints"],
            "payment_ready_count": fields["payment_ready_count"],
            "verified_count": fields["verified_count"],
            "traction": {
                "as_of": saved["source_traction_as_of_utc"],
                "measured_services": fields["measured_services"],
                "unique_buyers_30d": fields["unique_buyer_addresses_30d"],
                "settlement_count_30d": fields["settlement_count_30d"],
                "volume_usd_30d": fields["volume_usd_30d"],
                "top_1_service_share_pct": fields["top_1_service_share_pct"],
                "top_10_services_share_pct": fields["top_10_services_share_pct"],
                "top_1_service_top_buyer_share_pct": fields["top_1_service_top_buyer_share_pct"],
                "top_1_service_imported": fields["top_1_service_imported"],
                "coverage_of_measured_flow_pct": fields["coverage_of_measured_flow_pct"],
                "measured_flow_freshness": fields["measured_flow_freshness_at_computation"],
            },
        },
        "provenance": {
            "cite_as": saved["source_url"],
            "license": saved["source_license"],
            "attribution": saved["attribution"],
        },
    }


class DatedPublisherEvidenceTests(unittest.TestCase):
    def test_dated_concentration_replay_and_zero_agentmine_revenue_claim(self):
        actual = summarize(publisher_payload(), fetched_at="2026-10-26T23:59:00Z")
        self.assertEqual(actual["listed_services"], 1001)
        self.assertEqual(actual["publisher_settlements_30d"], 1832366)
        self.assertEqual(actual["publisher_implied_top1_buyer_share_of_listed_flow_pct"], "70.15")
        self.assertEqual(actual["flow_outside_top10_usd_30d"], "14440.56")
        self.assertEqual(actual["hypothetical_1pct_fee_on_all_outside_top10_usd_30d"], "144.41")
        self.assertEqual(actual["publisher_measured_flow_coverage_pct"], "18.1")
        self.assertEqual(actual["publisher_ingest_freshness_at_computation"], "NO_REPORTED_STALE_GROUPS")
        self.assertTrue(actual["top1_data_imported"])
        self.assertIsNone(actual["verified_paying_customers"])
        self.assertIsNone(actual["verified_agentmine_revenue_usd"])

    def test_rejects_inconsistent_publisher_sync_group_counts(self):
        payload = publisher_payload()
        payload["data"]["traction"]["measured_flow_freshness"]["stale_sync_groups"] = 52
        with self.assertRaisesRegex(ValueError, "stale groups exceed"):
            summarize(payload, fetched_at="2026-10-26T23:59:00Z")


if __name__ == "__main__":
    unittest.main()
