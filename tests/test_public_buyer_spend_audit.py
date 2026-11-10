import copy
import json
from pathlib import Path
import unittest

from src.public_buyer_spend_audit import analyze


FIXTURE = Path(__file__).resolve().parents[1] / "data/evidence/uk_procurement_intelligence_buyer_spend_2026-11-10.json"


class PublicBuyerSpendAuditTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_primary_selected_records(self):
        result = analyze(self.snapshot)
        totals = result["separate_financial_evidence"]
        self.assertEqual(totals["reported_payment"], {"records": 2, "amount_pence": 600000})
        self.assertEqual(totals["purchase_order"]["amount_pence"], 600000)
        self.assertEqual(totals["contract_document"]["amount_pence"], 1200000)
        self.assertEqual(totals["signed_contract_notice"]["amount_pence"], 2280000)
        self.assertEqual(result["payer_reported_payment_buyer_count"], 1)
        self.assertEqual(result["buyer_supplier_pairs_with_multiple_payment_dates"], 1)
        self.assertEqual(result["payment_date_spans_days"], [343])
        self.assertFalse(result["complete_payment_history"])
        for key in ("verified_subscription_renewals", "verified_supplier_revenue", "market_concentration", "verified_agentmine_customers", "verified_agentmine_revenue"):
            self.assertIsNone(result[key])

    def test_duplicate_record_rejected(self):
        self.snapshot["records"].append(copy.deepcopy(self.snapshot["records"][0]))
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_same_date_does_not_prove_repeat_dates(self):
        self.snapshot["records"][1]["event_date"] = self.snapshot["records"][0]["event_date"]
        self.assertEqual(analyze(self.snapshot)["buyer_supplier_pairs_with_multiple_payment_dates"], 0)

    def test_order_cannot_be_relabelled_payment(self):
        self.snapshot["records"][2]["kind"] = "reported_payment"
        self.snapshot["records"][2]["amount_basis"] = "published_net_amount"
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_contract_cannot_be_relabelled_payment(self):
        self.snapshot["records"][3]["kind"] = "reported_payment"
        self.snapshot["records"][3]["amount_basis"] = "published_net_amount"
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_invalid_amount_and_future_event(self):
        for amount in (True, -1, 0, 1.5, "300000"):
            with self.subTest(amount=amount):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["records"][0]["amount_pence"] = amount
                with self.assertRaises(ValueError):
                    analyze(snapshot)
        self.snapshot["records"][0]["event_date"] = "2026-11-11"
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_source_spoof_rejected(self):
        self.snapshot["records"][0]["source_url"] = "https://www.greatermanchester-ca.gov.uk.example.com/media/report.pdf"
        with self.assertRaises(ValueError):
            analyze(self.snapshot)


if __name__ == "__main__":
    unittest.main()
