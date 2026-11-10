import copy
import json
from pathlib import Path
import unittest

from src.agentanbud_usage_audit import audit


FIXTURE = Path(__file__).resolve().parents[1] / "data/evidence/agentanbud_usage_loop_audit_2026-11-10.json"


class AgentanbudUsageAuditTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(FIXTURE.read_text())

    def test_exact_public_snapshot(self):
        result = audit(self.snapshot)
        self.assertEqual(result["listed_raw_tool_calls"], 458974)
        self.assertEqual(result["publisher_headline_reconstructed_mcp_calls"], 458974)
        self.assertTrue(result["tool_table_reconciles_with_headline"])
        self.assertEqual(result["publisher_loop_share_pct"], 99.7237)
        self.assertEqual(result["publisher_retained_share_pct"], 0.2763)
        self.assertEqual(result["raw_nonsearch_tool_calls"], 155)
        self.assertEqual(result["raw_search_tool_share_pct"], 99.9662)

    def test_separate_sector_and_channel_denominators(self):
        result = audit(self.snapshot)
        self.assertEqual(result["raw_segment_event_total"], 482282)
        self.assertEqual(result["raw_it_segment_share_pct"], 16.7464)
        self.assertEqual(result["publisher_web_rest_searches"], 65901)
        self.assertEqual(result["publisher_rest_share_of_web_rest_pct"], 96.5069)

    def test_no_paid_or_filtered_identity_inference(self):
        result = audit(self.snapshot)
        self.assertEqual(result["publisher_agent_identity_buckets_before_loop_filter"], 983)
        for key in ("filtered_tool_mix", "verified_distinct_buyers", "verified_paid_demand", "verified_revenue"):
            self.assertIsNone(result[key])

    def test_nonreconciling_headline_does_not_report_loop_share(self):
        self.snapshot["headline"]["excluded_loop_calls"] += 1
        result = audit(self.snapshot)
        self.assertFalse(result["tool_table_reconciles_with_headline"])
        self.assertIsNone(result["publisher_loop_share_pct"])

    def test_truncated_table_is_not_complete(self):
        self.snapshot["tool_table_limit"] = len(self.snapshot["tool_counts"])
        result = audit(self.snapshot)
        self.assertFalse(result["tool_table_complete"])
        self.assertIsNone(result["tool_table_reconciles_with_headline"])
        self.assertIsNone(result["raw_nonsearch_tool_calls"])
        self.assertIsNone(result["publisher_loop_share_pct"])

    def test_bad_counts_rejected(self):
        for value in (True, -1, 1.5, "2"):
            with self.subTest(value=value):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["headline"]["retained_mcp_calls"] = value
                with self.assertRaises(ValueError):
                    audit(snapshot)

    def test_unknown_segment_or_tool_rejected(self):
        for key, value in (("segment_counts", "raw_search_label"), ("tool_counts", "invalid tool name")):
            with self.subTest(key=key):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot[key][value] = 1
                with self.assertRaises(ValueError):
                    audit(snapshot)

    def test_source_scope_and_revision_required(self):
        for key, value in (("source_url", "https://example.com"), ("scope", "30d"), ("publisher_code_sha", "bad"), ("observed_on", "2026-11-31")):
            with self.subTest(key=key):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot[key] = value
                with self.assertRaises(ValueError):
                    audit(snapshot)

    def test_zero_counts_do_not_divide_by_zero(self):
        for key in ("headline", "tool_counts", "segment_counts"):
            self.snapshot[key] = dict.fromkeys(self.snapshot[key], 0)
        result = audit(self.snapshot)
        self.assertTrue(result["tool_table_reconciles_with_headline"])
        self.assertIsNone(result["publisher_loop_share_pct"])
        self.assertIsNone(result["raw_it_segment_share_pct"])


if __name__ == "__main__":
    unittest.main()
