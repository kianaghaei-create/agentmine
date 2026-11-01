"""Offline synthetic eForms fixtures; not a claim to have fetched TED originals."""
import unittest
from src.eforms_deadline_parser import parse_deadlines

CAC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'


def fixture(date='2026-09-29+02:00', time='23:59:00+02:00',
            period='TenderSubmissionDeadlinePeriod', lot='LOT-0001'):
    return (f'<ContractNotice xmlns:cac="{CAC}" xmlns:cbc="{CBC}">'
            f'<cac:ProcurementProjectLot><cbc:ID>{lot}</cbc:ID>'
            f'<cac:TenderingProcess><cac:{period}>'
            f'<cbc:EndDate>{date}</cbc:EndDate><cbc:EndTime>{time}</cbc:EndTime>'
            f'</cac:{period}></cac:TenderingProcess></cac:ProcurementProjectLot>'
            f'</ContractNotice>')


class EformsDeadlineTests(unittest.TestCase):
    def test_2359_local_not_previous_utc_day(self):
        result = parse_deadlines(fixture())
        row = result['records'][0]
        self.assertEqual(row['deadline_utc'], '2026-09-29T21:59:00Z')
        self.assertEqual(row['date_only_midnight_utc_day'], '2026-09-28')
        self.assertTrue(row['date_only_midnight_differs_from_full_utc'])
        self.assertIsNone(result['verified_operative_legal_deadlines'])

    def test_application_stage_midnight_local_crosses_utc_day(self):
        row = parse_deadlines(fixture('2026-10-05+02:00', '00:00:00+02:00',
                                      'ParticipationRequestReceptionPeriod'))['records'][0]
        self.assertEqual(row['stage'], 'participation_request')
        self.assertEqual(row['deadline_utc'], '2026-10-04T22:00:00Z')
        self.assertFalse(row['date_only_midnight_differs_from_full_utc'])

    def test_utc_z_and_numeric_zero_interchangeable(self):
        row = parse_deadlines(fixture('2026-10-06Z', '21:59:59+00:00'))['records'][0]
        self.assertEqual(row['deadline_utc'], '2026-10-06T21:59:59Z')
        self.assertEqual(row['date_only_midnight_utc_day'], '2026-10-06')

    def test_different_offsets_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'offsets differ'):
            parse_deadlines(fixture('2026-09-29+02:00', '23:59:00Z'))

    def test_missing_time_and_naive_date_rejected(self):
        with self.assertRaises(ValueError):
            parse_deadlines(fixture().replace('<cbc:EndTime>23:59:00+02:00</cbc:EndTime>', ''))
        with self.assertRaises(ValueError):
            parse_deadlines(fixture('2026-09-29', '23:59:00+02:00'))

    def test_bad_calendar_and_hour_rejected(self):
        for date, time in [('2026-02-30+01:00', '12:00:00+01:00'),
                           ('2026-10-05+02:00', '24:00:00+02:00')]:
            with self.subTest(date=date, time=time), self.assertRaises(ValueError):
                parse_deadlines(fixture(date, time))

    def test_multiple_lots_kept_separate(self):
        xml = fixture(lot='LOT-0001').replace('</ContractNotice>', '') + (
            fixture(lot='LOT-0002', period='ParticipationRequestReceptionPeriod')
            .split('<cac:ProcurementProjectLot>')[1].split('</ContractNotice>')[0]
            .join(['<cac:ProcurementProjectLot>', '</ContractNotice>']))
        result = parse_deadlines(xml)
        self.assertEqual(result['parsed_lot_stage_deadlines'], 2)
        self.assertEqual({x['lot_id'] for x in result['records']}, {'LOT-0001', 'LOT-0002'})

    def test_duplicate_stage_periods_rejected(self):
        xml = fixture().replace('</cac:TenderingProcess>',
            '<cac:TenderSubmissionDeadlinePeriod><cbc:EndDate>2026-09-30+02:00</cbc:EndDate>'
            '<cbc:EndTime>23:59:00+02:00</cbc:EndTime>'
            '</cac:TenderSubmissionDeadlinePeriod></cac:TenderingProcess>')
        with self.assertRaisesRegex(ValueError, 'duplicate stage'):
            parse_deadlines(xml)

    def test_no_lot_deadline_does_not_invent_one(self):
        with self.assertRaisesRegex(ValueError, 'no supported'):
            parse_deadlines('<ContractNotice/>')

    def test_dtd_entity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DTD'):
            parse_deadlines('<!DOCTYPE foo><ContractNotice/>')

    def test_xml_size_limit(self):
        with self.assertRaisesRegex(ValueError, 'oversized'):
            parse_deadlines(' ' * 2_000_001)

    def test_malformed_xml_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid XML'):
            parse_deadlines('<ContractNotice>')


    def test_duplicate_enddate_rejected_even_if_first_value_valid(self):
        xml = fixture().replace(
            '</cbc:EndDate>',
            '</cbc:EndDate><cbc:EndDate>2026-09-30+02:00</cbc:EndDate>', 1)
        with self.assertRaisesRegex(ValueError, 'ambiguous or missing EndDate'):
            parse_deadlines(xml)

    def test_duplicate_endtime_rejected_even_if_first_value_valid(self):
        xml = fixture().replace(
            '</cbc:EndTime>',
            '</cbc:EndTime><cbc:EndTime>12:00:00+02:00</cbc:EndTime>', 1)
        with self.assertRaisesRegex(ValueError, 'ambiguous or missing EndTime'):
            parse_deadlines(xml)

    def test_duplicate_tendering_process_rejected_even_when_second_empty(self):
        xml = fixture().replace(
            '</cac:ProcurementProjectLot>',
            '<cac:TenderingProcess></cac:TenderingProcess></cac:ProcurementProjectLot>', 1)
        with self.assertRaisesRegex(ValueError, 'duplicate TenderingProcess'):
            parse_deadlines(xml)

    def test_empty_first_process_does_not_hide_second_deadline(self):
        xml = fixture().replace(
            '<cac:TenderingProcess>',
            '<cac:TenderingProcess></cac:TenderingProcess><cac:TenderingProcess>', 1)
        with self.assertRaisesRegex(ValueError, 'duplicate TenderingProcess'):
            parse_deadlines(xml)


if __name__ == '__main__':
    unittest.main()
