import unittest
from src.agentmine_cost_router import choose

PARAMS = dict(max_age_seconds=60, min_quality=0.8, max_total_usd='1')
VALID = dict(provider='provider-a', license_allowed=True, verified=True,
             age_seconds=5, quality=0.9, source_usd='0.05',
             tokens_usd='0.01', network_usd='0.01', source_url='https://example.org/data')

class MalformedQuoteTests(unittest.TestCase):
    def test_none_is_ignored(self):
        self.assertEqual(choose([None], **PARAMS)['status'], 'no_eligible_quote')

    def test_non_mapping_is_ignored(self):
        self.assertEqual(choose(['broken', 42, []], **PARAMS)['status'], 'no_eligible_quote')

    def test_bad_row_does_not_hide_valid_quote(self):
        self.assertEqual(choose([None, VALID], **PARAMS)['selected'], 'provider-a')

    def test_rejects_invalid_age_policy_even_with_no_quotes(self):
        for value in (True, -1, float('nan'), float('inf'), '60'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose([], max_age_seconds=value, min_quality=0.8, max_total_usd='1')

    def test_rejects_invalid_quality_policy_even_with_no_quotes(self):
        for value in (True, -0.1, 1.1, float('nan'), float('inf'), '0.8'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose([], max_age_seconds=60, min_quality=value, max_total_usd='1')

    def test_rejects_invalid_spending_budget_even_with_no_quotes(self):
        for value in (True, -1, 'Infinity', 'NaN', float('inf'), 'bad'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose([], max_age_seconds=60, min_quality=0.8, max_total_usd=value)

    def test_rejects_nonfinite_quote_age_and_quality(self):
        for key, value in (('age_seconds', float('inf')),
                           ('age_seconds', float('nan')),
                           ('quality', float('inf')),
                           ('quality', float('nan')),
                           ('quality', -0.01)):
            with self.subTest(key=key, value=value):
                q = {**VALID, key: value}
                self.assertEqual(choose([q], max_age_seconds=60,
                                        min_quality=0, max_total_usd='1')['status'],
                                 'no_eligible_quote')

    def test_exact_budget_boundary(self):
        self.assertEqual(choose([VALID], max_age_seconds=60,
                                min_quality=0.8, max_total_usd='0.07')['selected'],
                         'provider-a')
        self.assertEqual(choose([VALID], max_age_seconds=60,
                                min_quality=0.8, max_total_usd='0.069')['status'],
                         'no_eligible_quote')

    def test_does_not_modify_inputs(self):
        quotes = [None, VALID.copy()]
        choose(quotes, **PARAMS)
        self.assertEqual(quotes, [None, VALID])
