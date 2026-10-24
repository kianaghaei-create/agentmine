"""Stage-aware, conservative regression coverage for public procurement displays."""
import copy
import unittest
from src.deadline_evidence_triage import triage


def row(day, *, stage='unknown', label='unknown', kind='third_party', host='example.org'):
    return {'publication_number': '699156-2026', 'source_kind': kind,
            'source_url': f'https://{host}/notice/{day.replace(":", "-")}',
            'reported_deadline': day, 'stage_claim': stage,
            'display_label_claim': label}


def bundle(*rows):
    return {'publication_number': '699156-2026', 'observations': list(rows)}


class StageTests(unittest.TestCase):
    def test_same_stage_different_dates_needs_primary_review(self):
        result = triage(bundle(row('2026-11-06', stage='participation_request'),
                               row('2026-11-07', stage='participation_request')))
        self.assertEqual(result['same_stage_display_conflict_stages'], ['participation_request'])
        self.assertEqual(result['stage_aware_triage_status'], 'same_stage_display_conflict_needs_primary_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_different_known_stages_not_automatically_conflicting(self):
        result = triage(bundle(row('2026-11-06', stage='participation_request'),
                               row('2026-12-07', stage='bid_submission')))
        self.assertTrue(result['calendar_label_disagreement'])
        self.assertEqual(result['same_stage_display_conflict_stages'], [])
        self.assertEqual(result['stage_aware_triage_status'], 'different_stages_not_directly_comparable')

    def test_unknown_stage_outlier_requires_review_not_legal_claim(self):
        result = triage(bundle(row('2026-11-06', stage='participation_request'),
                               row('2027-01-09', stage='unknown')))
        self.assertEqual(result['unknown_stage_calendar_dates'], ['2027-01-09'])
        self.assertEqual(result['stage_aware_triage_status'], 'unknown_stage_discrepancy_needs_primary_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_botkyrka_stage_mislabel_requires_review(self):
        r = row('2026-11-06', stage='participation_request', label='participation_deadline',
                kind='official_buyer_submission_portal', host='www.kommersannons.se')
        q = row('2026-11-06', label='bid_deadline', kind='third_party_summary', host='licitera.se')
        result = triage(bundle(r, q))
        self.assertEqual(result['stage_label_review_source_urls'], [q['source_url']])
        self.assertTrue(result['submission_portal_present'])
        self.assertFalse(result['original_ted_notice_present'])

    def test_legacy_missing_stage_fields_supported(self):
        a = row('2026-10-30'); b = row('2026-10-31')
        a.pop('stage_claim'); a.pop('display_label_claim')
        b.pop('stage_claim'); b.pop('display_label_claim')
        self.assertEqual(triage(bundle(a,b))['triage_status'], 'manual_primary_source_review')

    def test_timestamp_date_labels_not_converted_to_utc(self):
        result = triage(bundle(row('2026-11-06T23:59:00+01:00'), row('2026-11-06')))
        self.assertFalse(result['calendar_label_disagreement'])
        self.assertIn('offset_timestamp', result['display_formats'])

    def test_bad_stage_and_label_rejected(self):
        for changes in ({'stage_claim':'final'}, {'display_label_claim':'signed_contract'}):
            with self.subTest(changes=changes):
                r = row('2026-11-06'); r.update(changes)
                with self.assertRaisesRegex(ValueError, 'stage or deadline label'):
                    triage(bundle(r))

    def test_invalid_or_duplicated_sources_rejected(self):
        r = row('2026-11-06')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            triage(bundle(r, copy.deepcopy(r)))
        r['source_url'] = 'http://example.org'
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            triage(bundle(r))

    def test_original_ted_host_enforced(self):
        r = row('2026-11-06', kind='original_ted_notice')
        with self.assertRaisesRegex(ValueError, 'TED host'):
            triage(bundle(r))
        r['source_url'] = 'https://ted.europa.eu/en/notice/-/detail/699156-2026'
        self.assertTrue(triage(bundle(r))['original_ted_notice_present'])

    def test_no_paid_demand_or_legal_deadline_claim(self):
        result = triage(bundle(row('2026-11-06')))
        self.assertIsNone(result['verified_agentmine_customers'])
        self.assertIsNone(result['authoritative_deadline'])
        self.assertFalse(result['legal_deadline_verified'])


    def test_same_day_different_hours_cannot_be_agreement(self):
        result = triage(bundle(row('2026-11-06T09:00:00+01:00', stage='participation_request'),
                               row('2026-11-06T17:00:00+01:00', stage='participation_request')))
        self.assertFalse(result['calendar_label_disagreement'])
        self.assertEqual(result['same_stage_instant_conflict_stages'], ['participation_request'])
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_equal_instants_in_different_offsets_not_conflict(self):
        result = triage(bundle(row('2026-11-06T09:00:00+01:00', stage='participation_request'),
                               row('2026-11-06T08:00:00Z', stage='participation_request')))
        self.assertEqual(result['same_stage_instant_conflict_stages'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')

    def test_cross_midnight_equal_utc_instant_not_false_conflict(self):
        result = triage(bundle(row('2026-11-06T23:30:00-02:00', stage='bid_submission'),
                               row('2026-11-07T01:30:00Z', stage='bid_submission')))
        self.assertTrue(result['calendar_label_disagreement'])
        self.assertEqual(result['same_stage_display_conflict_stages'], [])
        self.assertEqual(result['stage_aware_triage_status'], 'equivalent_utc_instant_different_calendar_labels')

    def test_same_stage_mixed_precision_requires_review(self):
        result = triage(bundle(row('2026-11-06', stage='bid_submission'),
                               row('2026-11-06T17:00:00+01:00', stage='bid_submission')))
        self.assertEqual(result['mixed_precision_review_stages'], ['bid_submission'])
        self.assertEqual(result['stage_aware_triage_status'], 'mixed_precision_requires_primary_review')
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')

    def test_different_stages_different_times_no_same_stage_conflict(self):
        result = triage(bundle(row('2026-11-06T09:00:00+01:00', stage='participation_request'),
                               row('2026-11-06T17:00:00+01:00', stage='bid_submission')))
        self.assertEqual(result['same_stage_instant_conflict_stages'], [])
        self.assertEqual(result['mixed_precision_review_stages'], [])


if __name__ == '__main__':
    unittest.main()
