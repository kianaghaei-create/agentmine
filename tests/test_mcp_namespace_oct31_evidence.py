"""Dated third-party MCP registry supply evidence; no buyer or revenue inference."""
import json
from pathlib import Path
import unittest

from src.mcp_namespace_bounds import analyze

BASE = Path(__file__).resolve().parents[1] / "data" / "evidence"
CURRENT = BASE / "mcp_registry_tanod_2026-10-31.json"
PREVIOUS = BASE / "mcp_registry_tanod_2026-10-27.json"


class October31RegistryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.current = json.loads(CURRENT.read_text(encoding="utf-8"))
        self.previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))

    def test_publisher_supply_subsets_and_status_reconcile(self):
        s = self.current["publisher_selected_fields"]
        self.assertEqual(s["remote_only"] + s["both_remote_and_package"], s["remote_servers"])
        self.assertEqual(s["remote_only"] + s["both_remote_and_package"]
                         + s["package_only"] + s["neither_remote_nor_package"],
                         s["server_names"])
        self.assertEqual(s["status_active_registry_label"]
                         + s["status_deprecated_registry_label"], s["server_names"])
        self.assertIsNone(s["liveness"])

    def test_namespace_bound_is_reproducible_and_not_supplier_hhi(self):
        s = self.current["publisher_selected_fields"]
        expected = self.current["derived_namespace_concentration_bounds"]
        result = analyze(server_names=s["server_names"],
                         namespace_labels=s["namespace_labels"],
                         largest_namespace_counts=[n for _, n in s["largest_15_namespace_labels"]])
        for result_key, evidence_key in [
            ("top_namespace_server_names", "top15_namespace_server_names"),
            ("top_namespace_listing_share_pct", "top15_share_pct"),
            ("unreported_namespace_server_names", "unreported_namespace_server_names"),
            ("unreported_namespace_labels", "unreported_namespace_labels"),
            ("hhi_lower_bound_exact_numerator", "hhi_lower_bound_exact_numerator"),
            ("hhi_lower_bound_exact_denominator", "hhi_lower_bound_exact_denominator"),
            ("hhi_lower_bound_floor_8dp", "hhi_lower_bound_floor_8dp"),
            ("effective_namespace_count_upper_bound_ceiling_2dp",
             "effective_namespace_count_upper_bound_ceiling_2dp"),
        ]:
            with self.subTest(field=result_key):
                observed = s[evidence_key] if evidence_key == "top15_namespace_server_names" else expected[evidence_key]
                self.assertEqual(result[result_key], observed)
        self.assertIsNone(result["verified_supplier_business_hhi"])
        self.assertIsNone(self.current["verified_agentmine_revenue_usd"])

    def test_four_day_change_is_reconciled_without_claiming_new_buyers(self):
        s = self.current["publisher_selected_fields"]
        p = self.previous["publisher_selected_fields"]
        change = self.current["comparison"]
        self.assertEqual(s["server_names"] - p["server_names"], change["server_names_absolute_delta"])
        self.assertEqual(s["namespace_labels"] - p["namespace_labels"], change["namespace_labels_absolute_delta"])
        self.assertEqual(s["remote_servers"] - p["remote_servers"], change["remote_servers_absolute_delta"])
        self.assertEqual(s["top15_namespace_server_names"] - p["top15_namespace_server_names"],
                         change["top15_server_names_delta_across_different_top15_sets"])
        self.assertIsNone(self.current["verified_agentmine_paying_customers"])
        self.assertIsNone(self.current["verified_agentmine_supplier_savings"])


if __name__ == "__main__":
    unittest.main()
