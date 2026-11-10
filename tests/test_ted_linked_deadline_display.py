import copy
import json
from pathlib import Path
import unittest

from src.ted_linked_deadline_display import audit, CHRONOLOGY, EVIDENCE, OLD, NEW

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    return tuple(json.loads((ROOT / p).read_text(encoding="utf-8")) for p in (CHRONOLOGY, EVIDENCE))


class LinkedDeadlineDisplayTests(unittest.TestCase):
    def test_real_selected_pages_and_scope(self):
        result = audit(*inputs())
        self.assertEqual(result["selected_rendered_pages"], 5)
        self.assertEqual(result["procedure_pages"], 2)
        self.assertEqual(result["procedure_headlines_matching_latest"], 1)
        self.assertEqual(result["procedure_headlines_matching_prior_not_latest"], 1)
        self.assertEqual(result["same_page_prior_headline_latest_detail_conflicts"], 1)
        self.assertEqual(result["notice_specific_headlines_matching_own_version"], 3)
        self.assertEqual(result["indexed_only_observations"], 1)
        self.assertTrue(result["indexed_date_matches_two_additional_information_mirrors_not_tender"])
        self.assertFalse(result["operative_deadline_verified"])
        self.assertIsNone(result["market_prevalence"])
        self.assertIsNone(result["verified_agentmine_revenue"])

    def test_historical_notice_is_not_stale_procedure(self):
        result = audit(*inputs())
        old_pages = [r for r in result["rows"] if r["notice_ids"] == [OLD]]
        self.assertEqual(len(old_pages), 2)
        self.assertTrue(all(r["headline_matches_comparison_notice"] for r in old_pages))
        self.assertTrue(all(not r["procedure_headline_matches_prior_not_latest"] for r in old_pages))

    def test_prior_headline_without_latest_detail_is_not_internal_conflict(self):
        chronology, evidence = inputs()
        evidence["pages"][0]["detail_dates"].pop(NEW)
        result = audit(chronology, evidence)
        self.assertEqual(result["procedure_headlines_matching_prior_not_latest"], 1)
        self.assertEqual(result["same_page_prior_headline_latest_detail_conflicts"], 0)

    def test_page_identity_scope_and_duplicate_fail_closed(self):
        chronology, evidence = inputs()
        for field, value in (("scope", "notice"), ("notice_ids", [OLD]), ("url", "https://example.org/"), ("access", "search_index_only"), ("lineage_reference", "wrong")):
            changed = copy.deepcopy(evidence)
            changed["pages"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(chronology, changed)
        evidence["pages"][1] = copy.deepcopy(evidence["pages"][0])
        with self.assertRaises(ValueError):
            audit(chronology, evidence)

    def test_wrong_chronology_or_delta_rejected(self):
        chronology, evidence = inputs()
        wrong = copy.deepcopy(chronology)
        wrong["source_snapshot_blob_sha"] = "0" * 40
        with self.assertRaises(ValueError):
            audit(wrong, evidence)
        chronology["change"]["deadline_change_seconds"] = 1
        with self.assertRaises(ValueError):
            audit(chronology, evidence)

    def test_indexed_excerpt_cannot_be_promoted(self):
        chronology, evidence = inputs()
        evidence["indexed_only"]["access"] = "rendered_public_page"
        with self.assertRaises(ValueError):
            audit(chronology, evidence)

    def test_mirror_disagreement_does_not_support_stage_hypothesis(self):
        chronology, evidence = inputs()
        evidence["additional_information_date_mirrors"][1]["displayed_calendar_date"] = "2026-08-21"
        self.assertFalse(audit(chronology, evidence)["indexed_date_matches_two_additional_information_mirrors_not_tender"])

    def test_portal_claim_and_invalid_date_rejected(self):
        chronology, evidence = inputs()
        changed = copy.deepcopy(evidence)
        changed["portal"]["access"] = "verified"
        with self.assertRaises(ValueError):
            audit(chronology, changed)
        evidence["pages"][0]["headline_date"] = "2026-02-30"
        with self.assertRaises(ValueError):
            audit(chronology, evidence)


if __name__ == "__main__":
    unittest.main()
