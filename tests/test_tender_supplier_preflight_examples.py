"""Historical examples are evidence cards, never supplier bid/no-bid decisions."""
import copy
import json
from pathlib import Path
import unittest
from src.tender_supplier_preflight_examples import build

EVIDENCE = Path(__file__).resolve().parents[1] / 'data' / 'evidence'
FILES = (
    'ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json',
    'ted_cpv72_search_projection_summary_2026-10-26.json',
    'ted_fixed20_upphandla_stage_visibility_2026-10-26.json',
    'ted_fixed20_primary_portal_stage_2026-10-26.json',
)


def real():
    return [json.loads((EVIDENCE / filename).read_text(encoding='utf-8')) for filename in FILES]


class HistoricalPreflightTests(unittest.TestCase):
    def test_three_actual_predeclared_examples_are_not_decisions(self):
        result = build(*real())
        self.assertEqual(result['example_count'], 3)
        self.assertEqual([r['publication_number'] for r in result['examples']],
                         ['600201-2026', '603727-2026', '610120-2026'])
        self.assertEqual([r['official_original_stage'] for r in result['examples']],
                         ['tender', 'participation_request', 'participation_request'])
        self.assertEqual([r['primary_it_cpv_48_or_72'] for r in result['examples']],
                         [False, True, False])
        self.assertEqual([r['primary_portal_stage_corroborated'] for r in result['examples']],
                         [False, True, False])
        self.assertTrue(all(r['supplier_bid_no_bid'] == 'UNDETERMINED' for r in result['examples']))
        self.assertEqual([r['competitor_examples_count'] for r in result['examples']], [2, 1, 1])
        self.assertTrue(all(claim['source_url'].startswith('https://')
                            for card in result['examples'] for claim in card['competitor_observations']))
        self.assertEqual(result['actual_paired_supplier_tasks'], 0)
        self.assertEqual(result['explicit_price_or_pilot_responses'], 0)
        self.assertIsNone(result['actual_supplier_time_saved_minutes'])
        self.assertIsNone(result['verified_paying_customers'])

    def test_published_cards_are_exactly_reproducible(self):
        published = json.loads((EVIDENCE / 'ted_three_historical_supplier_preflights_2026-10-26.json').read_text(encoding='utf-8'))
        self.assertEqual(published, build(*real()))

    def test_rejects_projection_stage_mismatch(self):
        args = real()
        for row in args[1]['rows']:
            if row['publication_number'] == '603727-2026':
                row['field_kind'] = 'deadline-receipt-tender-date-lot'
        with self.assertRaisesRegex(ValueError, 'primary stage mismatch'):
            build(*args)

    def test_rejects_false_portal_corroboration(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                row['portal_stage'] = 'tender'
        with self.assertRaisesRegex(ValueError, 'portal stage mismatch'):
            build(*args)

    def test_rejects_original_date_transcription_conflict(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '610120-2026':
                row['official_deadline_date'] = '2026-10-08'
        with self.assertRaisesRegex(ValueError, 'transcription mismatch'):
            build(*args)

    def test_rejects_missing_cohort_member(self):
        args = real()
        args[0]['notice_items'].pop()
        with self.assertRaisesRegex(ValueError, 'fixed-20 identity mismatch'):
            build(*args)

    def test_rejects_directory_url_substitution(self):
        args = real()
        for row in args[2]['directory_display_observations']:
            if row['publication_number'] == '600201-2026':
                row['source_url'] = 'https://example.org/600201-2026'
        with self.assertRaisesRegex(ValueError, 'not bound'):
            build(*args)

    def test_rejects_false_amendment_clearance(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                row['amendments_status'] = 'cleared'
        with self.assertRaisesRegex(ValueError, 'amendment clearance'):
            build(*args)

    def test_rejects_historical_example_used_as_current(self):
        with self.assertRaisesRegex(ValueError, 'not yet past'):
            build(*real(), as_of='2026-09-15')

    def test_rejects_future_as_of(self):
        with self.assertRaisesRegex(ValueError, 'future as_of'):
            build(*real(), as_of='2099-01-01')

    def test_rejects_fake_portal_corroboration_without_date(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                del row['portal_deadline_raw']
        with self.assertRaisesRegex(ValueError, 'portal deadline text missing'):
            build(*args)

    def test_rejects_fake_portal_corroboration_with_no_deadline_text(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                row['portal_deadline_raw'] = 'No deadline'
        with self.assertRaisesRegex(ValueError, 'public portal date token missing'):
            build(*args)

    def test_rejects_untrusted_primary_portal_url(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                row['portal_url'] = 'https://example.org/claim'
        with self.assertRaisesRegex(ValueError, 'untrusted source URL'):
            build(*args)

    def test_rejects_future_primary_observation(self):
        args = real()
        args[3]['observed_on_utc_date'] = '2099-01-01'
        with self.assertRaisesRegex(ValueError, 'future observation'):
            build(*args)

    def test_rejects_duplicate_official_projection(self):
        args = real()
        args[1]['rows'][1] = copy.deepcopy(args[1]['rows'][0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            build(*args)


if __name__ == '__main__':
    unittest.main()
