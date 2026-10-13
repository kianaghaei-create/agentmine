import unittest
from decimal import Decimal
from src.connect_payout_economics import connect_ticket_sensitivity_sek as calc


class ConnectEconomicsTests(unittest.TestCase):
    def test_single_small_ticket_is_loss(self):
        r = calc(ticket_sek="120")
        self.assertEqual(Decimal(r["modeled_contribution_before_unmodeled_costs_sek"]), Decimal("3.60") - Decimal("3.60") - Decimal("5.291") - Decimal("0.291") - Decimal("15"))

    def test_single_ticket_break_even(self):
        r = calc(ticket_sek="100")
        self.assertAlmostEqual(float(r["minimum_break_even_ticket_sek"]), 2147.78325123)

    def test_ten_transactions_single_payout_each(self):
        r = calc(ticket_sek="100", transactions_per_active_account_month=10)
        self.assertAlmostEqual(float(r["minimum_break_even_ticket_sek"]), 817.733990147)

    def test_batched_payouts_lower_fixed_cost(self):
        r = calc(ticket_sek="100", transactions_per_payout=10, transactions_per_active_account_month=100)
        self.assertAlmostEqual(float(r["minimum_break_even_ticket_sek"]), 241.379310345)

    def test_routing_is_optional(self):
        a = calc(ticket_sek="1000")
        b = calc(ticket_sek="1000", routing_rate_pct="0")
        self.assertGreater(Decimal(b["modeled_contribution_before_unmodeled_costs_sek"]), Decimal(a["modeled_contribution_before_unmodeled_costs_sek"]))

    def test_no_positive_margin_no_break_even(self):
        self.assertIsNone(calc(ticket_sek="100", take_rate_pct="1")["minimum_break_even_ticket_sek"])

    def test_zero_margin_zero_fixed_has_zero_break_even(self):
        r = calc(ticket_sek="100", take_rate_pct="1.5", card_rate_pct="1.5", card_fixed_sek="0", payout_rate_pct="0", payout_fixed_sek="0", routing_rate_pct="0", active_account_monthly_sek="0")
        self.assertEqual(Decimal(r["minimum_break_even_ticket_sek"]), 0)

    def test_input_validation(self):
        invalid = [{"ticket_sek": "NaN"}, {"ticket_sek": -1}, {"ticket_sek": 1.5}, {"ticket_sek": True}, {"take_rate_pct": "101"}, {"payout_rate_pct": "Infinity"}, {"transactions_per_payout": 0}, {"transactions_per_payout": True}, {"transactions_per_active_account_month": 0}, {"transactions_per_payout": 2, "transactions_per_active_account_month": 1}]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                calc(ticket_sek="10", **{k:v for k,v in kwargs.items() if k!='ticket_sek'}) if 'ticket_sek' not in kwargs else calc(**kwargs)

    def test_provenance_flags(self):
        r = calc(ticket_sek="200")
        self.assertIs(r["stripe_flow_and_rates_verified_for_agentmine"], False)
        self.assertIs(r["actual_payments_or_buyers_verified"], False)


if __name__ == "__main__":
    unittest.main()
