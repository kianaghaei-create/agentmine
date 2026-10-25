"""Offline title triage regression tests; synthetic names are never output."""
import unittest
from src.ted_title_gap_triage import triage


def row(name, day="2026-09-01"):
    return {"Publicerad": day, "Titel": name, "Internt id": "private"}


def notice(name, day="2026-09-01"):
    return {"publication-date": day, "notice-title": name, "publication-number": "secret"}


class TitleGapTriageTests(unittest.TestCase):
    def test_unique_same_day_title_is_only_candidate(self):
        result = triage([row("Secure cloud migration")], [notice({"eng": " secure  CLOUD migration "})])
        self.assertEqual(result["title_candidate_categories"], {"one_same_date_title_candidate_not_identity": 1})
        self.assertIsNone(result["verified_same_procurement_entities"])
        self.assertNotIn("Secure cloud", str(result))
        self.assertNotIn("secret", str(result))

    def test_ambiguous_title_collisions_are_not_identity(self):
        result = triage([row("Municipal data platform"), row("Municipal data platform")],
                        [notice("Municipal data platform")])
        self.assertEqual(result["title_candidate_categories"], {"multiple_same_date_title_candidates": 1})

    def test_same_title_other_date_is_not_same_date_match(self):
        result = triage([row("Municipal data platform")], [notice("Municipal data platform", "2026-09-02")])
        self.assertEqual(result["title_candidate_categories"], {"title_candidate_different_publication_date": 1})

    def test_no_match_and_missing_title_distinguished(self):
        result = triage([row("Unrelated software tender"), row("", "2026-09-02")],
                        [notice("A distinct procurement"), notice({"eng": "Short"})])
        self.assertEqual(result["title_candidate_categories"], {
            "missing_usable_ted_title": 1, "no_exact_normalized_title_candidate": 1})
        self.assertEqual(result["licitera_rows_with_usable_title"], 1)
        self.assertEqual(result["unmatched_ted_contract_notices_with_usable_title"], 1)

    def test_multilingual_title_and_unicode_normalization(self):
        result = triage([row("Data management services")],
                        [notice({"sv": "Helt annat namn", "en": "Data management services"})])
        self.assertEqual(result["title_candidate_categories"], {"one_same_date_title_candidate_not_identity": 1})

    def test_nested_language_list(self):
        result = triage([row("Data management services")],
                        [notice({"eng": ["Data management services"]})])
        self.assertEqual(result["title_candidate_categories"], {"one_same_date_title_candidate_not_identity": 1})

    def test_invalid_date_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "invalid TED publication date"):
            triage([row("Data management services")], [notice("Data management services", "bad")])
        with self.assertRaisesRegex(ValueError, "invalid publication date"):
            triage([row("Data management services", "not a date")], [])

    def test_empty_cohort_not_invented(self):
        result = triage([row("Data management services")], [])
        self.assertEqual(result["unmatched_ted_contract_notices"], 0)
        self.assertEqual(result["title_candidate_categories"], {})


if __name__ == "__main__":
    unittest.main()
