"""Synthetic economics fixtures: no real settlements, costs, or paid demand."""
from decimal import Decimal
import unittest

from src.x402_settlement_cost_floor import analyze


class SettlementCostFloorTests(unittest.TestCase):
    def test_monthly_overhead_changes_actual_modeled_break_even(self):
        result = analyze(monthly_settlements=100, ticket_usd='1',
                         take_rate_pct='3', included_settlements=0,
                         facilitator_fee_usd='0.001',
                         fulfillment_per_settlement_usd='0.01',
                         monthly_overhead_usd='10')
        self.assertEqual(Decimal(result['modeled_variable_cost_usd']), Decimal('1.1'))
        self.assertEqual(Decimal(result['modeled_monthly_overhead_usd']), Decimal('10'))
        self.assertEqual(Decimal(result['minimum_ticket_to_cover_modeled_variable_costs_usd']),
                         Decimal('1.1') / Decimal('3'))
        self.assertEqual(Decimal(result['minimum_ticket_to_cover_all_modeled_costs_usd']),
                         Decimal('3.7'))
        self.assertEqual(Decimal(result['modeled_monthly_contribution_before_unmodeled_costs_usd']),
                         Decimal('-8.1'))
        self.assertIsNone(result['verified_agentmine_paying_customers'])

    def test_full_modeled_break_even_has_zero_contribution(self):
        result = analyze(monthly_settlements=100, ticket_usd='3.7',
                         take_rate_pct='3', included_settlements=0,
                         facilitator_fee_usd='0.001',
                         fulfillment_per_settlement_usd='0.01',
                         monthly_overhead_usd='10')
        self.assertEqual(Decimal(result['modeled_monthly_contribution_before_unmodeled_costs_usd']),
                         Decimal('0'))

    def test_no_settlements_cannot_cover_monthly_overhead(self):
        result = analyze(monthly_settlements=0, ticket_usd='1000',
                         take_rate_pct='50', monthly_overhead_usd='10')
        self.assertIsNone(result['minimum_ticket_to_cover_modeled_variable_costs_usd'])
        self.assertIsNone(result['minimum_ticket_to_cover_all_modeled_costs_usd'])
        self.assertEqual(Decimal(result['modeled_monthly_contribution_before_unmodeled_costs_usd']),
                         Decimal('-10'))

    def test_zero_take_and_zero_costs_break_even_at_zero(self):
        result = analyze(monthly_settlements=20, ticket_usd='1',
                         take_rate_pct='0', included_settlements=20,
                         facilitator_fee_usd='0', monthly_overhead_usd='0')
        self.assertEqual(Decimal(result['minimum_ticket_to_cover_modeled_variable_costs_usd']),
                         Decimal('0'))
        self.assertEqual(Decimal(result['minimum_ticket_to_cover_all_modeled_costs_usd']),
                         Decimal('0'))

    def test_zero_take_cannot_recover_positive_overhead(self):
        result = analyze(monthly_settlements=20, ticket_usd='100',
                         take_rate_pct='0', included_settlements=20,
                         facilitator_fee_usd='0', monthly_overhead_usd='1')
        self.assertEqual(Decimal(result['minimum_ticket_to_cover_modeled_variable_costs_usd']),
                         Decimal('0'))
        self.assertIsNone(result['minimum_ticket_to_cover_all_modeled_costs_usd'])

    def test_zero_take_cannot_recover_positive_variable_cost(self):
        result = analyze(monthly_settlements=20, ticket_usd='100',
                         take_rate_pct='0', included_settlements=0,
                         facilitator_fee_usd='0.001', monthly_overhead_usd='0')
        self.assertIsNone(result['minimum_ticket_to_cover_modeled_variable_costs_usd'])
        self.assertIsNone(result['minimum_ticket_to_cover_all_modeled_costs_usd'])

    def test_no_overhead_makes_both_floors_equal(self):
        result = analyze(monthly_settlements=100, ticket_usd='1',
                         take_rate_pct='2', included_settlements=0,
                         facilitator_fee_usd='0.001', monthly_overhead_usd='0')
        self.assertEqual(result['minimum_ticket_to_cover_modeled_variable_costs_usd'],
                         result['minimum_ticket_to_cover_all_modeled_costs_usd'])


if __name__ == '__main__':
    unittest.main()
