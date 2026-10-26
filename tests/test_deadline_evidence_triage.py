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


    def test_unknown_stage_same_day_conflicting_hours_requires_review(self):
        result = triage(bundle(row('2026-11-06T09:00:00+01:00'),
                               row('2026-11-06T17:00:00+01:00')))
        self.assertFalse(result['calendar_label_disagreement'])
        self.assertEqual(result['unknown_stage_time_discrepancy_calendar_dates'], ['2026-11-06'])
        self.assertEqual(result['stage_aware_triage_status'], 'unknown_stage_time_discrepancy_needs_primary_review')
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertEqual(result['same_stage_display_conflict_stages'], [])

    def test_unknown_stage_hour_differs_from_known_stage_requires_review(self):
        result = triage(bundle(row('2026-11-06T09:00:00+01:00', stage='participation_request'),
                               row('2026-11-06T17:00:00+01:00')))
        self.assertEqual(result['unknown_stage_time_discrepancy_calendar_dates'], ['2026-11-06'])
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_unknown_stage_same_instant_different_offsets_is_not_time_conflict(self):
        result = triage(bundle(row('2026-11-06T09:00:00+01:00', stage='participation_request'),
                               row('2026-11-06T08:00:00Z')))
        self.assertEqual(result['unknown_stage_time_discrepancy_calendar_dates'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')

    def test_unknown_stage_same_day_date_only_does_not_invent_time_conflict(self):
        result = triage(bundle(row('2026-11-06', stage='participation_request'),
                               row('2026-11-06T17:00:00+01:00')))
        self.assertEqual(result['unknown_stage_time_discrepancy_calendar_dates'], [])
        self.assertFalse(result['legal_deadline_verified'])


    def test_unknown_bid_label_not_flagged_if_one_known_stage_matches(self):
        # Questions and bid submission may share a date. An unknown-stage
        # directory's bid label is supported by the explicit bid-stage row.
        official_questions = row('2026-11-06', stage='questions',
                                 label='questions_deadline', kind='official_buyer_submission_portal',
                                 host='questions.example.org')
        official_bid = row('2026-11-06', stage='bid_submission',
                           label='bid_deadline', kind='official_buyer_submission_portal',
                           host='bid.example.org')
        directory_bid = row('2026-11-06', stage='unknown',
                            label='bid_deadline', host='directory.example.org')
        result = triage(bundle(official_questions, official_bid, directory_bid))
        self.assertEqual(result['stage_label_review_source_urls'], [])
        self.assertEqual(result['stage_aware_triage_status'], 'stage_consistent_displays_unverified')
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')
        self.assertFalse(result['legal_deadline_verified'])

    def test_unknown_bid_label_flagged_when_no_known_stage_matches(self):
        official_questions = row('2026-11-06', stage='questions',
                                 label='questions_deadline', kind='official_buyer_submission_portal',
                                 host='questions.example.org')
        official_application = row('2026-11-06', stage='participation_request',
                                   label='participation_deadline', kind='official_buyer_submission_portal',
                                   host='apply.example.org')
        directory_bid = row('2026-11-06', stage='unknown',
                            label='bid_deadline', host='directory.example.org')
        result = triage(bundle(official_questions, official_application, directory_bid))
        self.assertEqual(result['stage_label_review_source_urls'], [directory_bid['source_url']])
        self.assertEqual(result['stage_aware_triage_status'], 'stage_label_requires_review')
        self.assertFalse(result['legal_deadline_verified'])


    def test_two_unverified_directory_stage_labels_same_date_need_review(self):
        licitera = row('2026-10-27', label='bid_deadline',
                       kind='third_party_summary', host='licitera.se')
        tilldelat = row('2026-10-27', label='participation_deadline',
                        kind='third_party_summary', host='tilldelat.se')
        result = triage(bundle(licitera, tilldelat))
        self.assertEqual(result['stage_label_review_source_urls'],
                         sorted([licitera['source_url'], tilldelat['source_url']]))
        self.assertEqual(result['stage_aware_triage_status'], 'stage_label_requires_review')
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])
        self.assertFalse(result['submission_portal_present'])

    def test_two_unverified_directories_agreeing_stage_label_not_flagged(self):
        first = row('2026-10-27', label='participation_deadline', host='first.example.org')
        second = row('2026-10-27', label='participation_deadline', host='second.example.org')
        result = triage(bundle(first, second))
        self.assertEqual(result['stage_label_review_source_urls'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')

    def test_generic_label_is_not_an_opposing_stage_claim(self):
        specific = row('2026-10-27', label='participation_deadline', host='first.example.org')
        generic = row('2026-10-27', label='generic_deadline', host='second.example.org')
        result = triage(bundle(specific, generic))
        self.assertEqual(result['stage_label_review_source_urls'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')


    def test_explicit_directory_bid_stage_cannot_launder_primary_application_stage(self):
        # A directory may self-assert a stage as well as its display label.
        # That assertion must not cancel the conflicting primary-stage claim.
        portal = row('2026-11-06', stage='participation_request',
                     label='participation_deadline',
                     kind='official_buyer_submission_portal', host='www.kommersannons.se')
        directory = row('2026-11-06', stage='bid_submission',
                        label='bid_deadline', kind='third_party_summary',
                        host='licitera.se')
        result = triage(bundle(portal, directory))
        self.assertEqual(result['stage_label_review_source_urls'], [directory['source_url']])
        self.assertEqual(result['stage_aware_triage_status'], 'stage_label_requires_review')
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_multiple_primary_stages_on_same_date_support_directory_stage(self):
        # Both stages can genuinely share a calendar date.
        portal = row('2026-11-06', stage='participation_request',
                     label='participation_deadline',
                     kind='official_buyer_submission_portal', host='www.kommersannons.se')
        ted = row('2026-11-06', stage='bid_submission', label='bid_deadline',
                  kind='original_ted_notice', host='ted.europa.eu')
        directory = row('2026-11-06', stage='bid_submission',
                        label='bid_deadline', kind='third_party_summary',
                        host='licitera.se')
        result = triage(bundle(portal, ted, directory))
        self.assertEqual(result['stage_label_review_source_urls'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')

    def test_official_summary_stage_does_not_override_primary_stage(self):
        portal = row('2026-11-06', stage='participation_request',
                     label='participation_deadline',
                     kind='official_buyer_submission_portal', host='www.kommersannons.se')
        summary = row('2026-11-06', stage='bid_submission', label='bid_deadline',
                      kind='official_summary', host='op.europa.eu')
        result = triage(bundle(portal, summary))
        self.assertEqual(result['stage_label_review_source_urls'], [summary['source_url']])
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])


    def test_two_explicit_unverified_directories_disagree_on_same_day(self):
        # Each directory's internally consistent stage/label must not validate
        # the other. This is a review candidate, not a legal deadline error.
        a = row('2026-10-27', stage='bid_submission', label='bid_deadline',
                kind='third_party_summary', host='licitera.se')
        b = row('2026-10-27', stage='participation_request',
                label='participation_deadline', kind='third_party_summary',
                host='tilldelat.se')
        result = triage(bundle(a, b))
        self.assertEqual(result['stage_label_review_source_urls'],
                         sorted([a['source_url'], b['source_url']]))
        self.assertEqual(result['stage_aware_triage_status'], 'stage_label_requires_review')
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_unknown_label_cannot_launder_conflicting_nonprimary_stages(self):
        # An additional unverified directory label cannot resolve two opposing
        # explicit non-primary claims. All remain review candidates.
        bid = row('2026-10-27', stage='bid_submission',
                  label='bid_deadline', host='bid.example.org')
        apply = row('2026-10-27', stage='participation_request',
                    label='participation_deadline', host='apply.example.org')
        unknown = row('2026-10-27', label='bid_deadline',
                      host='unknown.example.org')
        result = triage(bundle(bid, apply, unknown))
        self.assertEqual(result['stage_label_review_source_urls'],
                         sorted([bid['source_url'], apply['source_url']]))
        self.assertEqual(result['triage_status'], 'manual_primary_source_review')
        self.assertFalse(result['legal_deadline_verified'])

    def test_two_explicit_unverified_directories_agree_on_same_stage(self):
        a = row('2026-10-27', stage='participation_request',
                label='participation_deadline', host='first.example.org')
        b = row('2026-10-27', stage='participation_request',
                label='participation_deadline', host='second.example.org')
        result = triage(bundle(a, b))
        self.assertEqual(result['stage_label_review_source_urls'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')

    def test_two_primary_stages_support_distinct_directory_claims(self):
        # Separate official stages may legitimately share a date.
        primary_a = row('2026-10-27', stage='bid_submission', label='bid_deadline',
                        kind='original_ted_notice', host='ted.europa.eu')
        primary_b = row('2026-10-27', stage='participation_request',
                        label='participation_deadline',
                        kind='official_buyer_submission_portal',
                        host='buyer.example.org')
        directory_a = row('2026-10-27', stage='bid_submission', label='bid_deadline',
                          host='first.example.org')
        directory_b = row('2026-10-27', stage='participation_request',
                          label='participation_deadline', host='second.example.org')
        result = triage(bundle(primary_a, primary_b, directory_a, directory_b))
        self.assertEqual(result['stage_label_review_source_urls'], [])
        self.assertEqual(result['triage_status'], 'unverified_display_agreement')
        self.assertFalse(result['legal_deadline_verified'])


if __name__ == '__main__':
    unittest.main()
