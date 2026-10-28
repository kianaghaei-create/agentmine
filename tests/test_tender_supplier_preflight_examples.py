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
    def test_three_primary_it_examples_are_not_decisions(self):
        result = build(*real())
        self.assertEqual(result['example_count'], 3)
        self.assertEqual([r['publication_number'] for r in result['examples']],
                         ['603727-2026', '606049-2026', '609559-2026'])
        self.assertEqual([r['official_original_stage'] for r in result['examples']],
                         ['participation_request', 'participation_request', 'participation_request'])
        self.assertEqual([r['primary_it_cpv_48_or_72'] for r in result['examples']],
                         [True, True, True])
        self.assertEqual([r['primary_portal_stage_corroborated'] for r in result['examples']],
                         [True, True, False])
        self.assertTrue(all(r['supplier_bid_no_bid'] == 'UNDETERMINED' for r in result['examples']))
        self.assertEqual([r['competitor_examples_count'] for r in result['examples']], [1, 1, 1])
        self.assertTrue(all(claim['source_url'].startswith('https://')
                            for card in result['examples'] for claim in card['competitor_observations']))
        self.assertEqual(result['actual_paired_supplier_tasks'], 0)
        self.assertEqual(result['explicit_price_or_pilot_responses'], 0)
        self.assertIsNone(result['actual_supplier_time_saved_minutes'])
        self.assertIsNone(result['verified_paying_customers'])

    def test_published_cards_are_exactly_reproducible(self):
        published = json.loads((EVIDENCE / 'ted_three_primary_it_supplier_preflights_2026-10-28.json').read_text(encoding='utf-8'))
        self.assertEqual(published, build(*real()))

    def test_competitor_stage_displays_bind_to_same_notice(self):
        args = real()
        by_id = {r['publication_number']: r for r in args[2]['independent_competitor_observations']}
        for card in build(*args)['examples']:
            with self.subTest(notice=card['publication_number']):
                self.assertEqual(card['competitor_examples_count'], 1)
                self.assertEqual(card['competitor_observations'][0]['source_url'],
                                 by_id[card['publication_number']]['source_url'])
                self.assertIn(by_id[card['publication_number']]['displayed_date'],
                              card['competitor_observations'][0]['public_display'])

    def test_duplicate_competitor_stage_observation_is_rejected(self):
        args = real()
        duplicate = copy.deepcopy(next(row for row in args[2]['independent_competitor_observations']
                                       if row['publication_number'] == '609559-2026'))
        args[2]['independent_competitor_observations'].append(duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate independent competitor display'):
            build(*args)

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
            if row['publication_number'] == '609559-2026':
                row['official_deadline_date'] = '2026-10-08'
        with self.assertRaisesRegex(ValueError, 'original raw date contradicts normalized original date'):
            build(*args)

    def test_rejects_missing_cohort_member(self):
        args = real()
        args[0]['notice_items'].pop()
        with self.assertRaisesRegex(ValueError, 'fixed-20 identity mismatch'):
            build(*args)

    def test_rejects_directory_url_substitution(self):
        args = real()
        for row in args[2]['directory_display_observations']:
            if row['publication_number'] == '603727-2026':
                row['source_url'] = 'https://example.org/600201-2026'
        with self.assertRaisesRegex(ValueError, 'unbound directory source'):
            build(*args)

    def test_rejects_false_amendment_clearance(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                row['amendments_status'] = 'cleared'
        with self.assertRaisesRegex(ValueError, 'unverified amendment status must not claim clearance'):
            build(*args)

    def test_rejects_historical_example_used_as_current(self):
        with self.assertRaisesRegex(ValueError, 'not yet past'):
            build(*real(), as_of='2026-09-15')

    def test_selection_is_first_three_primary_it_originals_not_cherry_picked(self):
        args = real()
        original_ids = {row['publication_number'] for row in args[3]['observations']}
        eligible = sorted(row['publication_number'] for row in args[1]['rows']
                          if row['publication_number'] in original_ids
                          and row['procedure_main_cpv'].startswith(('48', '72')))
        self.assertEqual(eligible[:3], ['603727-2026', '606049-2026', '609559-2026'])
        for row in args[1]['rows']:
            if row['publication_number'] == '609559-2026':
                row['procedure_main_cpv'] = '79000000'
        with self.assertRaisesRegex(ValueError, 'selected IT preflight cohort'):
            build(*args)

    def test_rejects_private_or_primary_competitor_source(self):
        for url in ("https://127.0.0.1/upphandling/example",
                    "https://localhost/upphandling/example",
                    "https://ted.europa.eu/sv/notice/603727-2026/html",
                    "https://upphandla.app/en/tender/603727-2026"):
            with self.subTest(url=url):
                args = real()
                next(r for r in args[2]['independent_competitor_observations']
                     if r['publication_number'] == '603727-2026')['source_url'] = url
                with self.assertRaisesRegex(ValueError, 'invalid independent competitor source URL'):
                    build(*args)

    def test_rejects_non_tender_competitor_page_or_ambiguous_url(self):
        for url in ("https://tilldelat.se/",
                    "https://tilldelat.se/upphandling/",
                    "https://tilldelat.se/upphandling/real?other=603727-2026",
                    "https://user:pass@tilldelat.se/upphandling/real",
                    "https://tilldelat.se:444/upphandling/real"):
            with self.subTest(url=url):
                args = real()
                next(r for r in args[2]['independent_competitor_observations']
                     if r['publication_number'] == '603727-2026')['source_url'] = url
                with self.assertRaisesRegex(ValueError, 'invalid independent competitor source URL'):
                    build(*args)

    def test_rejects_cross_notice_competitor_url_substitution(self):
        args = real()
        rows = {r['publication_number']: r
                for r in args[2]['independent_competitor_observations']}
        rows['603727-2026']['source_url'] = rows['606049-2026']['source_url']
        with self.assertRaisesRegex(ValueError, 'competitor URL not bound to notice'):
            build(*args)

    def test_rejects_unreviewed_but_well_formed_tilldelat_detail(self):
        args = real()
        next(r for r in args[2]['independent_competitor_observations']
             if r['publication_number'] == '603727-2026')['source_url'] = (
                 'https://tilldelat.se/upphandling/plausible-but-unverified-123456')
        with self.assertRaisesRegex(ValueError, 'competitor URL not bound to notice'):
            build(*args)

    def test_rejects_unbound_fallback_even_with_display_text(self):
        args = real()
        args[2]['independent_competitor_observations'] = [
            row for row in args[2]['independent_competitor_observations']
            if row['publication_number'] != '603727-2026'
        ]
        original = next(r for r in args[3]['observations']
                        if r['publication_number'] == '603727-2026')
        original['competitor_url'] = 'https://tilldelat.se/upphandling/eventnat-99e715'
        original['competitor_observation'] = 'Sista ansökningsdag 9 oktober 2026'
        with self.assertRaisesRegex(ValueError, 'competitor URL not bound to notice'):
            build(*args)

    def test_reviewed_fallback_remains_allowed(self):
        args = real()
        reviewed = next(r for r in args[2]['independent_competitor_observations']
                        if r['publication_number'] == '603727-2026')
        args[2]['independent_competitor_observations'] = [
            row for row in args[2]['independent_competitor_observations']
            if row['publication_number'] != '603727-2026'
        ]
        original = next(r for r in args[3]['observations']
                        if r['publication_number'] == '603727-2026')
        original['competitor_url'] = reviewed['source_url']
        original['competitor_observation'] = 'Sista ansökningsdag 9 oktober 2026'
        result = build(*args)
        self.assertEqual(result['examples'][0]['competitor_observations'][0]['source_url'],
                         reviewed['source_url'])

    def test_rejects_unstructured_competitor_date(self):
        for bad in ("October 9", "2026-10-09 customer@example.com", "2026-13-09", None):
            with self.subTest(date=bad):
                args = real()
                next(r for r in args[2]['independent_competitor_observations']
                     if r['publication_number'] == '603727-2026')['displayed_date'] = bad
                with self.assertRaisesRegex(ValueError, 'competitor display date'):
                    build(*args)

    def test_rejects_untrusted_fallback_competitor_url(self):
        args = real()
        args[2]['independent_competitor_observations'] = [
            row for row in args[2]['independent_competitor_observations']
            if row['publication_number'] != '603727-2026'
        ]
        next(r for r in args[3]['observations']
             if r['publication_number'] == '603727-2026')['competitor_url'] = (
                 "https://127.0.0.1/upphandling/fake")
        with self.assertRaisesRegex(ValueError, 'invalid independent competitor source URL'):
            build(*args)

    def test_rejects_fallback_without_display_observation(self):
        args = real()
        args[2]['independent_competitor_observations'] = [
            row for row in args[2]['independent_competitor_observations']
            if row['publication_number'] != '603727-2026'
        ]
        next(r for r in args[3]['observations']
             if r['publication_number'] == '603727-2026')['competitor_url'] = (
                 "https://tilldelat.se/upphandling/valid-page")
        with self.assertRaisesRegex(ValueError, 'invalid competitor display evidence'):
            build(*args)

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

    def test_rejects_false_corroboration_with_unrelated_portal_date(self):
        args = real()
        for row in args[3]['observations']:
            if row['publication_number'] == '603727-2026':
                row['portal_deadline_raw'] = 'Final day for applications 11/9/2026'
        with self.assertRaisesRegex(ValueError, 'portal date conflicts with original'):
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
