"""Offline option-claim audit regressions; no external calls or customer data."""
import json
from pathlib import Path
import unittest
from src.tender_option_claim_audit import audit

EVIDENCE = Path(__file__).resolve().parents[1] / "data/evidence/ted_fixed20_615392_option_claim_2026-10-28.json"


def fixture():
    return {
        "evidence_type": "public_original_vs_directory_option_claim",
        "observed_on_utc_date": "2026-10-28",
        "publication_number": "615392-2026",
        "official_url": "https://ted.europa.eu/sv/notice/615392-2026/html",
        "directory_url": "https://upphandla.app/en/tender/615392-2026",
        "portal_access": "login_required", "amendments_verified": False,
        "official_option_clauses": [
            {"option_id": "OPT-1", "original_excerpt": "Pris för Option 1 ingår i utvärderingen.", "included_in_evaluation": True, "voluntary": False},
            {"option_id": "OPT-2", "original_excerpt": "Option 2 ... (frivillig) Pris för Option 2 ingår inte i utvärderingen.", "included_in_evaluation": False, "voluntary": True},
        ],
        "directory_claim": {"summary_excerpt": "Two options are mandatory in the evaluation: handling for hourly staff and administration of receipts and reimbursements.", "claimed_mandatory_in_evaluation_option_ids": ["OPT-1", "OPT-2"], "human_mapping_not_independently_verified": True}
    }


class Tests(unittest.TestCase):
    def test_one_source_backed_conflict_not_legal_error(self):
        result = audit(fixture())
        self.assertEqual(result['official_evaluation_excluded_or_voluntary_option_ids'], ['OPT-2'])
        self.assertTrue(result['directory_original_display_claim_conflict'])
        self.assertFalse(result['legally_operative_requirement_verified'])
        self.assertIsNone(result['verified_agentmine_customers'])

    def test_no_conflict_when_claim_matches(self):
        x = fixture(); x['directory_claim']['claimed_mandatory_in_evaluation_option_ids'] = ['OPT-1']
        x['directory_claim']['summary_excerpt'] = 'One option is mandatory in the evaluation: handling for hourly staff.'
        self.assertFalse(audit(x)['directory_original_display_claim_conflict'])

    def test_rejects_fabricated_official_inclusion(self):
        x = fixture(); x['official_option_clauses'][1]['included_in_evaluation'] = True
        with self.assertRaisesRegex(ValueError, 'inclusion lacks source anchor'):
            audit(x)

    def test_rejects_fabricated_voluntary(self):
        x = fixture(); x['official_option_clauses'][0]['voluntary'] = True
        with self.assertRaisesRegex(ValueError, 'voluntary flag lacks source anchor'):
            audit(x)

    def test_rejects_missing_official_exclusion(self):
        x = fixture(); x['official_option_clauses'][1]['original_excerpt'] = 'Option 2 (frivillig) can be offered.'
        with self.assertRaisesRegex(ValueError, 'exclusion lacks source anchor'):
            audit(x)

    def test_rejects_count_mapping_disagreement(self):
        x = fixture(); x['directory_claim']['claimed_mandatory_in_evaluation_option_ids'] = ['OPT-1']
        with self.assertRaisesRegex(ValueError, 'count and mapped'):
            audit(x)

    def test_rejects_duplicate_option(self):
        x = fixture(); x['official_option_clauses'][1]['option_id'] = 'OPT-1'
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            audit(x)

    def test_rejects_unbound_sources(self):
        for key, url in [('official_url','https://ted.europa.eu/sv/notice/111111-2026/html'), ('directory_url','https://upphandla.app/en/tender/111111-2026')]:
            x = fixture(); x[key] = url
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'not bound'):
                audit(x)

    def test_rejects_future_and_unsupported_portal_clearance(self):
        x = fixture(); x['observed_on_utc_date'] = '2099-01-01'
        with self.assertRaisesRegex(ValueError, 'future'):
            audit(x)
        x = fixture(); x['amendments_verified'] = True
        with self.assertRaisesRegex(ValueError, 'clearance'):
            audit(x)

    def test_rejects_unanchored_summary_and_unsupported_mapping(self):
        x = fixture(); x['directory_claim']['summary_excerpt'] = 'Some options could be used.'
        with self.assertRaisesRegex(ValueError, 'not source anchored'):
            audit(x)
        x = fixture(); x['directory_claim']['human_mapping_not_independently_verified'] = False
        with self.assertRaisesRegex(ValueError, 'not source anchored'):
            audit(x)

    def test_rejects_duplicate_mapping_and_unknown_option(self):
        for ids in (['OPT-2','OPT-2'],['OPT-9']):
            x = fixture(); x['directory_claim']['claimed_mandatory_in_evaluation_option_ids'] = ids
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, 'mapping'):
                audit(x)

    def test_committed_public_evidence_reproducible_and_commercially_null(self):
        saved = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(saved["audit_input"], fixture())
        self.assertEqual(saved["audit_result"], audit(saved["audit_input"]))
        self.assertEqual(saved["fixed20_cumulative_primary_originals_checked"], 15)
        self.assertEqual(saved["fixed20_denominator"], 20)
        self.assertEqual(saved["fixed20_amendment_histories_cleared"], 0)
        self.assertIsNone(saved["commercial_outcomes"]["verified_agentmine_customers"])
        self.assertIsNone(saved["commercial_outcomes"]["actual_supplier_minutes_saved"])


if __name__ == '__main__':
    unittest.main()
