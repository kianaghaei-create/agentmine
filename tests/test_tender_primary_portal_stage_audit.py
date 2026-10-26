"""Regression coverage for fail-closed primary source vs public directory audit."""
import copy
import unittest
from datetime import datetime, timezone

from src.tender_primary_portal_stage_audit import audit


def fixtures():
    ids = [f"{600000 + i}-2026" for i in range(20)]
    cohort = {"complete_frame_reconciled": True, "cohort_size": 20,
              "query": "fixed-query", "notice_items": [{"publication_number": n} for n in ids]}
    official = {"complete_current_query_frame": True, "missing_cohort_count": 0,
                "query": "fixed-query", "observed_at_utc": "2026-10-26T10:00:00Z",
                "rows": [{"publication_number": n, "field_kind": "deadline-receipt-request-date-lot"} for n in ids]}
    directory = {"official_projection_observed_at_utc": official["observed_at_utc"],
                 "directory_display_observations": [
                     {"publication_number": n, "source_url": f"https://upphandla.app/en/tender/{n}",
                      "display_status": "no_deadline_displayed"} for n in ids]}
    primary = {"evidence_type": "fixed20_primary_portal_stage_observations",
               "observed_on_utc_date": "2026-10-26",
               "observations": [{
                   "publication_number": ids[0],
                   "official_notice_url": f"https://ted.europa.eu/sv/notice/{ids[0]}/html",
                   "official_stage": "participation_request",
                   "official_deadline_date": "2026-10-01",
                   "official_deadline_raw": "01/10/2026 23:59 UTC+02",
                   "portal_url": "https://www.kommersannons.se/eLite/Notice/NoticeOverview.aspx?ProcurementId=72841",
                   "portal_status": "public_stage_and_date_text",
                   "portal_stage": "participation_request",
                   "portal_deadline_raw": "10/1/2026",
                   "portal_date_interpretation": "unverified_locale",
                   "amendments_status": "not_checked"
               }]}
    return cohort, official, directory, primary


class PrimaryPortalStageAuditTests(unittest.TestCase):
    def test_primary_stage_agrees_directory_missing_date_fixed_denominator(self):
        result = audit(*fixtures())
        self.assertEqual(result["fixed_cohort_count"], 20)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 1)
        self.assertEqual(result["original_notice_observed_count"], 1)
        self.assertEqual(result["primary_portal_unverified_count"], 19)
        self.assertEqual(result["verified_operative_deadline_errors"], 0)
        self.assertIsNone(result["verified_paying_customers"])

    def test_inaccessible_portal_never_counts_as_verified(self):
        args = fixtures()
        row = args[3]["observations"][0]
        row["portal_status"] = "not_observed_tool_access"
        for field in ("portal_stage", "portal_deadline_raw", "portal_date_interpretation"):
            row.pop(field, None)
        result = audit(*args)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 0)
        self.assertEqual(result["primary_portal_unverified_count"], 20)

    def test_conflicting_portal_stage_is_not_omission(self):
        args = fixtures()
        args[3]["observations"][0]["portal_stage"] = "tender"
        result = audit(*args)
        self.assertEqual(result["public_portal_stage_conflicts_count"], 1)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 0)

    def test_official_projection_conflict_is_not_omission(self):
        args = fixtures()
        args[1]["rows"][0]["field_kind"] = "deadline-receipt-tender-date-lot"
        result = audit(*args)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 0)
        self.assertEqual(result["status_counts"]["original_projection_stage_conflict"], 1)

    def test_no_directory_omission_when_directory_has_date(self):
        args = fixtures()
        args[2]["directory_display_observations"][0]["display_status"] = "date_displayed"
        result = audit(*args)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 0)

    def test_duplicate_primary_rejected(self):
        args = fixtures()
        args[3]["observations"].append(copy.deepcopy(args[3]["observations"][0]))
        with self.assertRaises(ValueError):
            audit(*args)

    def test_noncohort_primary_rejected(self):
        args = fixtures()
        args[3]["observations"][0]["publication_number"] = "999999-2026"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_untrusted_portal_host_rejected(self):
        args = fixtures()
        args[3]["observations"][0]["portal_url"] = "https://example.org/claim"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_portal_missing_raw_date_rejected(self):
        args = fixtures()
        args[3]["observations"][0]["portal_deadline_raw"] = ""
        with self.assertRaises(ValueError):
            audit(*args)

    def test_cannot_claim_amendments_verified(self):
        args = fixtures()
        args[3]["observations"][0]["amendments_status"] = "checked_no_changes"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_portal_label_without_date_cannot_count_as_corrobation(self):
        args = fixtures()
        args[3]["observations"][0]["portal_deadline_raw"] = "No deadline"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_portal_stage_text_without_date_cannot_count(self):
        args = fixtures()
        args[3]["observations"][0]["portal_deadline_raw"] = "Final day for applications"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_original_transcription_conflicting_with_iso_date_rejected(self):
        args = fixtures()
        args[3]["observations"][0]["official_deadline_raw"] = "09/10/2026 23:59 UTC+02"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_ambiguous_portal_locale_retained_without_normalization(self):
        args = fixtures()
        args[3]["observations"][0]["portal_deadline_raw"] = "Final day for applications 10/1/2026"
        result = audit(*args)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 1)
        self.assertFalse(result["items"][0]["operative_deadline_verified"])

    def test_future_observation_rejected(self):
        args = fixtures()
        args[3]["observed_on_utc_date"] = "2099-01-01"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_wrong_directory_provenance_rejected(self):
        args = fixtures()
        args[2]["official_projection_observed_at_utc"] = "2026-10-25T10:00:00Z"
        with self.assertRaises(ValueError):
            audit(*args)

    def test_official_eavrop_access_denied_keeps_portal_unverified(self):
        args = fixtures()
        row = args[3]["observations"][0]
        row["portal_url"] = "https://www.e-avrop.com/vasteras/e-Upphandling/NoticeLink.aspx?id=120492"
        row["portal_status"] = "not_observed_tool_access"
        for field in ("portal_stage", "portal_deadline_raw", "portal_date_interpretation"):
            row.pop(field, None)
        result = audit(*args)
        self.assertEqual(result["original_notice_observed_count"], 1)
        self.assertEqual(result["primary_portal_unverified_count"], 20)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 0)

    def test_tendsign_login_does_not_count_as_public_portal_verification(self):
        args = fixtures()
        row = args[3]["observations"][0]
        row["portal_url"] = "https://tendsign.com/doc.aspx?MeFormsNoticeId=98869&GoTo=Tender"
        row["portal_status"] = "not_observed_tool_access"
        for field in ("portal_stage", "portal_deadline_raw", "portal_date_interpretation"):
            row.pop(field, None)
        result = audit(*args)
        self.assertEqual(result["original_notice_observed_count"], 1)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 0)
        self.assertEqual(result["primary_portal_unverified_count"], 20)

    def test_committed_public_evidence_fixed20_integration(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "data" / "evidence"
        def load(name):
            return json.loads((root / name).read_text(encoding="utf-8"))
        result = audit(
            load("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json"),
            load("ted_cpv72_search_projection_summary_2026-10-26.json"),
            load("ted_fixed20_upphandla_stage_visibility_2026-10-26.json"),
            load("ted_fixed20_primary_portal_stage_2026-10-26.json"),
        )
        self.assertEqual(result["fixed_cohort_count"], 20)
        self.assertEqual(result["original_notice_observed_count"], 5)
        self.assertEqual(result["public_portal_stage_agrees_directory_no_date_count"], 2)
        self.assertEqual(result["primary_portal_unverified_count"], 18)
        self.assertEqual(result["amendments_checked_count"], 0)
        self.assertEqual(result["verified_operative_deadline_errors"], 0)


if __name__ == "__main__":
    unittest.main()
