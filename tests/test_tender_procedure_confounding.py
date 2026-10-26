"""Tests fixed-cohort procedure/stage confounding without inventing legal deadlines."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.tender_procedure_confounding import analyze

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence"


def load(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


class ConfoundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = load("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json")
        cls.official = load("ted_cpv72_search_projection_summary_2026-10-26.json")
        cls.directory = load("ted_fixed20_upphandla_stage_visibility_2026-10-26.json")
        cls.procedures = load("ted_fixed20_procedure_confounding_2026-10-26.json")

    def run_audit(self, procedures=None, official=None, directory=None):
        return analyze(self.cohort, official or self.official, directory or self.directory, procedures or self.procedures)

    def test_real_cohort_procedure_confounding(self):
        r = self.run_audit()
        self.assertEqual(r["fixed_notices"], 20)
        self.assertEqual(r["procedure_labels_observed"], 19)
        self.assertEqual(r["procedure_labels_unavailable"], 1)
        self.assertEqual(r["source_counts"], {"tenderiva.com": 1, "upphandla.app": 18})
        self.assertEqual(r["stage_by_procedure"], {
            "participation_request__negotiated_with_prior_publication": 7,
            "participation_request__restricted_selective": 1,
            "tender__open": 11,
        })
        self.assertEqual(r["stage_by_directory_visibility_with_procedure_observed"], {
            "participation_request__no_deadline_displayed": 8,
            "tender__date_displayed": 11,
        })
        self.assertFalse(r["open_vs_nonopen_stage_overlap"])
        self.assertFalse(r["stage_cause_identifiable_from_this_cohort"])
        self.assertIsNone(r["verified_paying_customers"])

    def test_missing_observation_not_silently_dropped(self):
        p = deepcopy(self.procedures)
        p["procedure_observations"].pop()
        with self.assertRaisesRegex(ValueError, "20 fixed"):
            self.run_audit(procedures=p)

    def test_duplicate_notice_rejected(self):
        p = deepcopy(self.procedures)
        p["procedure_observations"][1] = p["procedure_observations"][0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_audit(procedures=p)

    def test_cross_notice_url_rejected(self):
        p = deepcopy(self.procedures)
        p["procedure_observations"][0]["source_url"] = "https://upphandla.app/en/tender/999999-2026"
        with self.assertRaisesRegex(ValueError, "not bound"):
            self.run_audit(procedures=p)

    def test_unapproved_host_rejected(self):
        p = deepcopy(self.procedures)
        p["procedure_observations"][0]["source_url"] = "https://other.example/en/tender/600201-2026"
        with self.assertRaisesRegex(ValueError, "unapproved"):
            self.run_audit(procedures=p)

    def test_raw_label_must_match_claimed_procedure(self):
        p = deepcopy(self.procedures)
        p["procedure_observations"][0]["procedure_kind"] = "negotiated_with_prior_publication"
        with self.assertRaisesRegex(ValueError, "raw label"):
            self.run_audit(procedures=p)

    def test_unknown_procedure_must_remain_unavailable(self):
        p = deepcopy(self.procedures)
        p["procedure_observations"][1]["observation_status"] = "label_observed"
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.run_audit(procedures=p)

    def test_official_stage_not_invented(self):
        official = deepcopy(self.official)
        official["rows"][0]["field_kind"] = "invented"
        with self.assertRaisesRegex(ValueError, "unknown official stage"):
            self.run_audit(official=official)

    def test_query_frame_must_match(self):
        official = deepcopy(self.official)
        official["query"] = "other"
        with self.assertRaisesRegex(ValueError, "query differs"):
            self.run_audit(official=official)

    def test_procedure_overlap_does_not_prove_causality(self):
        p = deepcopy(self.procedures)
        row = next(x for x in p["procedure_observations"] if x["publication_number"] == "600201-2026")
        row["procedure_kind"] = "negotiated_with_prior_publication"
        row["raw_procedure_label"] = "Förhandlat förfarande med föregående annonsering"
        r = self.run_audit(procedures=p)
        self.assertTrue(r["open_vs_nonopen_stage_overlap"])
        self.assertFalse(r["stage_cause_identifiable_from_this_cohort"])


if __name__ == "__main__":
    unittest.main()
