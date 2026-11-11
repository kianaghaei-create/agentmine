import copy
import json
from pathlib import Path
import unittest

from src.eu_ppa_proposal_risk import EVIDENCE, audit, screen


class EUProposalRiskTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((Path(__file__).resolve().parents[1] / EVIDENCE).read_text(encoding="utf-8"))

    def run_screen(self, **changes):
        args = dict(network_platform=False, supplier_only=True, fee_basis="separate_analytics", data_basis="existing_public")
        args.update(changes)
        return screen(self.snapshot, **args)

    def test_proposal_budget_not_enacted_or_appropriated(self):
        result = audit(self.snapshot)
        self.assertEqual(result["indicative_budget_eur"], 163437000)
        self.assertFalse(result["budget_is_approved_spend"])
        self.assertIsNone(result["application_date"])
        self.assertIsNone(result["verified_agentmine_revenue"])
        self.assertFalse(result["current_law_assessed"])

    def test_network_access_fee_and_procurement_detail_fee(self):
        for fee in ("network_communication_access", "procurement_detail_access"):
            with self.subTest(fee=fee):
                self.assertEqual(self.run_screen(network_platform=True, fee_basis=fee)["fee_screen"], "proposed_access_fee_conflict")
                self.assertEqual(self.run_screen(fee_basis=fee)["fee_screen"], "review_scope_and_access_fee")

    def test_supplier_only_exception_is_connection_only(self):
        result = self.run_screen(network_platform=True)
        self.assertEqual(result["nppds_connection"], "proposed_supplier_only_connection_exception")
        self.assertIn("eea_ownership_control_storage", result["other_proposed_platform_duties"])
        self.assertIn("free_network_communication_access", result["other_proposed_platform_duties"])
        self.assertEqual(self.run_screen(network_platform=True, supplier_only=False)["nppds_connection"], "proposed_nppds_connection_required")

    def test_separate_analytics_and_private_fee_not_automatically_banned_or_cleared(self):
        for fee in ("separate_analytics", "private_transaction_fee"):
            with self.subTest(fee=fee):
                result = self.run_screen(fee_basis=fee)
                self.assertEqual(result["fee_screen"], "not_the_express_access_fee_ban_no_clearance")
                self.assertFalse(result["legal_clearance"])
                self.assertFalse(result["launch_authorized"])
                self.assertEqual(result["scope"], "proposal_platform_definition_not_demonstrated")

    def test_future_reporting_is_not_public_or_reuse_access(self):
        self.assertEqual(self.run_screen(data_basis="future_contract_reporting")["data_access_screen"], "proposed_reporting_not_public_availability_or_reuse")
        self.assertEqual(self.run_screen(data_basis="nonpublic_ppds")["data_access_screen"], "restricted_requires_designation_and_authorized_access")
        self.assertEqual(self.run_screen()["data_access_screen"], "existing_source_rights_review_separate")

    def test_changed_status_dates_and_budget_rejected(self):
        for section, key, value in (("proposal", "status", "enacted"), ("proposal", "application_date", "2030-01-01"),
                                    ("budget", "basis", "paid"), ("budget", "total_eur", 163437001)):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad[section][key] = value
                with self.assertRaises(ValueError):
                    audit(bad)

    def test_provision_overstatement_or_type_confusion_rejected(self):
        for key, value in (("nonpublic_data_access_restricted", False), ("contract_reporting_threshold_eur", True),
                           ("network_communication_access_fee_prohibited", 1)):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad["provisions"][key]["value"] = value
                with self.assertRaises(ValueError):
                    audit(bad)

    def test_invalid_scenario_rejected(self):
        for changes in ({"network_platform": 1}, {"supplier_only": "yes"}, {"fee_basis": "unknown"}, {"data_basis": []}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.run_screen(**changes)


if __name__ == "__main__":
    unittest.main()
