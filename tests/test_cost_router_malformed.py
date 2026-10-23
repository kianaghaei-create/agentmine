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

    def test_does_not_modify_inputs(self):
        quotes = [None, VALID.copy()]
        choose(quotes, **PARAMS)
        self.assertEqual(quotes, [None, VALID])
