"""Offline tests of official procedure identity signals (synthetic only)."""
import unittest
from src.ted_procedure_gap_triage import triage

P1 = "11111111-1111-4111-8111-111111111111"
P2 = "22222222-2222-4222-8222-222222222222"


def notice(number, proc=None, previous=None):
    return {"publication-number": number, "procedure-identifier": proc,
            "previous-notice-id-proc": previous}


class ProcedureGapTriageTests(unittest.TestCase):
    def test_shared_procedure_and_previous_reference_are_separate_signals(self):
        matched = notice("000001-2026", P1)
        missing = notice("000002-2026", P1, ["000001-2026"])
        result = triage([matched, missing], {"000001-2026"}, [missing])
        self.assertEqual(result["procedure_cohort_categories"],
                         {"same_procedure_as_exact_matched_notice": 1})
        self.assertEqual(result["unmatched_contract_notices_explicitly_referring_to_matched_publication"], 1)
        self.assertIsNone(result["verified_licitera_product_search_misses"])
        self.assertNotIn(P1, str(result))
        self.assertNotIn("000002-2026", str(result))

    def test_missing_and_distinct_procedures_not_called_identity(self):
        matched = notice("000001-2026", P1)
        a = notice("000002-2026")
        b = notice("000003-2026", P2)
        result = triage([matched, a, b], {"000001-2026"}, [a, b])
        self.assertEqual(result["procedure_cohort_categories"], {
            "missing_procedure_identifier": 1,
            "no_same_procedure_in_matched_september_cohort": 1})
        self.assertEqual(result["unmatched_contract_notices_with_procedure_identifier"], 1)

    def test_reverse_reference_and_unrecognized_previous_ignored(self):
        matched = notice("000001-2026", P1, ["000002-2026", "uuid-99"])
        missing = notice("000002-2026", P2, "uuid-99")
        result = triage([matched, missing], {"000001-2026"}, [missing])
        self.assertEqual(result["matched_notices_explicitly_referring_to_unmatched_contract_publication"], 1)
        self.assertEqual(result["unmatched_contract_notices_explicitly_referring_to_matched_publication"], 0)

    def test_accept_singleton_procedure_projection(self):
        matched = notice("000001-2026", [P1])
        missing = notice("000002-2026", P1)
        result = triage([matched, missing], {"000001-2026"}, [missing])
        self.assertEqual(result["matched_notices_with_procedure_identifier"], 1)

    def test_fail_closed_malformed_identifiers_and_references(self):
        matched = notice("000001-2026", P1)
        for bad in ("not-uuid", "11111111-1111-1111-8111-111111111111", {"x": P1}, [P1, P2]):
            missing = notice("000002-2026", bad)
            with self.assertRaises(ValueError):
                triage([matched, missing], {"000001-2026"}, [missing])
        missing = notice("000002-2026", P2, [3])
        with self.assertRaisesRegex(ValueError, "previous"):
            triage([matched, missing], {"000001-2026"}, [missing])

    def test_duplicate_and_outside_cohort_fail_closed(self):
        matched = notice("000001-2026", P1)
        missing = notice("000002-2026", P2)
        with self.assertRaises(ValueError):
            triage([matched, matched], {"000001-2026"}, [missing])
        with self.assertRaises(ValueError):
            triage([matched, missing], {"000003-2026"}, [missing])
        with self.assertRaises(ValueError):
            triage([matched, missing], {"000001-2026"}, [matched])

    def test_empty_unmatched_is_valid_and_not_misleading(self):
        matched = notice("000001-2026", P1)
        result = triage([matched], {"000001-2026"}, [])
        self.assertEqual(result["unmatched_contract_notices"], 0)
        self.assertEqual(result["procedure_cohort_categories"], {})
