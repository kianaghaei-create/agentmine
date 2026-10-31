"""TED OPP-010 publication identity must not be inferred from a URL alone.

All XML fixtures here are synthetic. They do not establish original access.
"""
import io
import unittest

from src.ted_primary_xml_review import fetch_xml, parse_notice, review_cohort

ROOT = 'urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2'
EFAC = 'http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1'
EFBC = 'http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1'


def xml_for(number=None, *, second=None):
    publications = []
    for value in (number, second):
        if value is not None:
            publications.append(
                f'<efac:Publication><efbc:NoticePublicationID schemeName="ojs-notice-id">'
                f'{value}</efbc:NoticePublicationID></efac:Publication>'
            )
    return (
        f'<ContractNotice xmlns="{ROOT}" xmlns:efac="{EFAC}" xmlns:efbc="{EFBC}">'
        + ''.join(publications) + '</ContractNotice>'
    ).encode('utf-8')


def cohort():
    return {
        'complete_frame_reconciled': True,
        'cohort_size': 20,
        'source_url': 'https://api.ted.europa.eu/v3/notices/search',
        'selection_rule': 'synthetic fixed twenty',
        'notice_items': [
            {'publication_number': f'{600201+i}-2026'} for i in range(20)
        ],
    }


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Opener:
    def __init__(self, payload):
        self.payload = payload

    def open(self, request, timeout):
        return Response(self.payload)


class PublicationIdentityTests(unittest.TestCase):
    def test_zero_padded_official_publication_id_binds_to_requested_number(self):
        parsed = parse_notice(xml_for('00600201-2026'), '600201-2026')
        self.assertTrue(parsed['xml_publication_identity_bound'])
        self.assertEqual(parsed['xml_publication_id'], '00600201-2026')
        self.assertTrue(fetch_xml('600201-2026', opener=Opener(xml_for('00600201-2026'))))

    def test_different_publication_number_rejected_in_parse_and_fetch(self):
        wrong = xml_for('00600202-2026')
        with self.assertRaisesRegex(ValueError, 'publication ID mismatch'):
            parse_notice(wrong, '600201-2026')
        with self.assertRaisesRegex(ValueError, 'publication ID mismatch'):
            fetch_xml('600201-2026', opener=Opener(wrong))

    def test_different_publication_year_rejected(self):
        with self.assertRaisesRegex(ValueError, 'publication ID mismatch'):
            parse_notice(xml_for('00600201-2025'), '600201-2026')

    def test_duplicate_and_malformed_official_metadata_rejected(self):
        for payload in (
            xml_for('00600201-2026', second='00600201-2026'),
            xml_for('00000000-2026'),
            xml_for('not-a-publication'),
        ):
            with self.subTest(payload=payload), self.assertRaisesRegex(
                ValueError, 'invalid or ambiguous TED publication metadata'
            ):
                parse_notice(payload, '600201-2026')

    def test_missing_publication_metadata_is_unbound_not_verified(self):
        parsed = parse_notice(xml_for(), '600201-2026')
        self.assertIsNone(parsed['xml_publication_id'])
        self.assertFalse(parsed['xml_publication_identity_bound'])
        result = review_cohort(cohort(), fetcher=lambda _: xml_for())
        self.assertEqual(result['original_xml_parsed_count'], 20)
        self.assertEqual(result['original_xml_publication_identity_bound_count'], 0)
        self.assertEqual(result['original_xml_parsed_identity_unbound_count'], 20)
        self.assertTrue(all(r['status'] == 'original_xml_parsed_identity_unbound'
                            for r in result['items']))

    def test_bound_cohort_counts_distinct_originals_and_rejects_wrong_body(self):
        result = review_cohort(
            cohort(), fetcher=lambda notice: xml_for(notice.split('-')[0].zfill(8)
                                                     + '-' + notice.split('-')[1])
        )
        self.assertEqual(result['original_xml_publication_identity_bound_count'], 20)
        self.assertEqual(result['original_xml_parsed_identity_unbound_count'], 0)
        wrong = review_cohort(cohort(), fetcher=lambda _: xml_for('00600201-2026'))
        self.assertEqual(wrong['original_xml_parsed_count'], 1)
        self.assertEqual(wrong['original_xml_unavailable_count'], 19)
        self.assertEqual(wrong['original_xml_publication_identity_bound_count'], 1)


if __name__ == '__main__':
    unittest.main()
