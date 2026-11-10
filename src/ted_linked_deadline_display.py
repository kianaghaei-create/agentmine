"""Compare selected public deadline displays with a verified TED notice change.

A notice-specific historical page is not a stale procedure-level headline.
Rendered pages may be cached; indexed-only observations are kept separate.
No legal cutoff, supplier outcome, prevalence or paid demand is established.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

CHRONOLOGY = "data/evidence/ted_fixed20_lifecycle_chronology_2026-11-10.json"
EVIDENCE = "data/evidence/ted_vaxjo_linked_deadline_display_2026-11-10.json"
SOURCE_SNAPSHOT = "data/evidence/ted_fixed20_lifecycle_metadata_2026-11-10.json"
SOURCE_BLOB = "260fae7eba80c3f149067c4f41fb7eadc3e8f91f"
OLD, NEW = "417627-2026", "601453-2026"
PROCEDURE = "93dd47eb-8036-40dd-b3a0-287e1818f0c5"
PRIOR_VERSION = "f8381887-5b8c-4f29-8943-4c380faba9b2-01"
PAGES = {
    "OpenProcurements": ("https://se.openprocurements.com/tender/mobiltelefoner-med-tillhorande-tjanster/", "procedure", (OLD, NEW)),
    "Licitera": ("https://licitera.se/upphandling/mobiltelefoner-med-tillhorande-tjanster-ae7cb81ee5", "procedure", (OLD, NEW)),
    "Evergabe": ("https://www.evergabe.com/sl/ponudbe/mobiltelefoner-med-tillhorande-tjanster-2298422/", "notice", (OLD,)),
    "Patterno": ("https://www.patterno.de/en/ausschreibungen/tender/mobiltelefone-und-zugehoerige-dienste-vaexjoe-qgrj8pus0x6ym89bf56y2jik", "notice", (OLD,)),
    "Tender Impulse": ("https://tenderimpulse.com/government-tenders/sweden/mobiltelefoner-med-tillh-rande-tj-nster-14632024", "notice", (NEW,)),
}
INDEX_URL = "https://tenderwize.com/en/tenders/417627-2026"
PORTAL = "https://tendsign.com/doc.aspx?MeFormsNoticeId=94800&GoTo=Tender"


def _day(value):
    if not isinstance(value, str):
        raise ValueError("calendar date required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid calendar date") from exc
    if parsed.isoformat() != value:
        raise ValueError("canonical calendar date required")
    return parsed


def _instant(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise ValueError("canonical UTC timestamp required")
    return parsed


def audit(chronology, evidence):
    if (chronology.get("evidence_type") != "derived_TED_Search_metadata_chronology_not_legal_or_exact_publication_time"
            or chronology.get("source_snapshot") != SOURCE_SNAPSHOT
            or chronology.get("source_snapshot_blob_sha") != SOURCE_BLOB
            or chronology.get("summary", {}).get("linked_change_comparisons") != 1):
        raise ValueError("expected verified frozen-cohort chronology")
    change = chronology.get("change", {})
    if (change.get("prior_publication_number"), change.get("change_publication_number")) != (OLD, NEW):
        raise ValueError("wrong linked notice pair")
    old, new = _instant(change.get("prior_deadline_utc")), _instant(change.get("new_deadline_utc"))
    if (new - old).total_seconds() != change.get("deadline_change_seconds") or new <= old:
        raise ValueError("inconsistent deadline change")
    # Both source UTC dates and Stockholm calendar dates are considered. A
    # date-only observation cannot distinguish timezone or exact cutoff.
    local = ZoneInfo("Europe/Stockholm")
    days = {OLD: {old.date(), old.astimezone(local).date()},
            NEW: {new.date(), new.astimezone(local).date()}}
    if days[OLD] & days[NEW]:
        raise ValueError("overlapping dates cannot distinguish this change")
    if (evidence.get("evidence_type") != "selected_public_linked_notice_deadline_displays"
            or evidence.get("chronology_path") != CHRONOLOGY
            or evidence.get("source_observed_at") != chronology.get("source_observed_at")
            or evidence.get("procedure_identifier") != PROCEDURE
            or evidence.get("portal") != {"url": PORTAL, "access": "login_required"}):
        raise ValueError("unbound evidence or unsupported portal claim")
    observed = _day(evidence.get("retrieved_on"))
    if observed > datetime.now(timezone.utc).date():
        raise ValueError("future retrieval date")
    rows = evidence.get("pages")
    if not isinstance(rows, list) or len(rows) != len(PAGES):
        raise ValueError("all selected public pages required")
    seen, results = set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid page")
        provider = row.get("provider")
        if provider not in PAGES or provider in seen:
            raise ValueError("unknown or duplicate public page")
        seen.add(provider)
        url, scope, ids = PAGES[provider]
        if (row.get("url") != url or row.get("scope") != scope
                or row.get("notice_ids") != list(ids)
                or row.get("access") != "rendered_public_page"):
            raise ValueError("page identity, scope or access mismatch")
        if provider == "OpenProcurements" and row.get("lineage_reference") != PRIOR_VERSION:
            raise ValueError("grouped history lacks exact prior notice-version reference")
        headline = _day(row.get("headline_date"))
        target = NEW if scope == "procedure" else ids[0]
        details = row.get("detail_dates")
        if not isinstance(details, dict) or not set(details) <= set(ids):
            raise ValueError("detail dates not bound to page notice IDs")
        detail_matches = {n: _day(v) in days[n] for n, v in details.items()}
        matches_target = headline in days[target]
        prior_not_latest = scope == "procedure" and headline in days[OLD] and not matches_target
        results.append({"provider": provider, "scope": scope, "notice_ids": list(ids),
                        "headline_date": headline.isoformat(), "comparison_notice_id": target,
                        "headline_matches_comparison_notice": matches_target,
                        "procedure_headline_matches_prior_not_latest": prior_not_latest,
                        "same_page_latest_detail_matches_source": detail_matches.get(NEW),
                        "same_page_prior_headline_latest_detail_conflict": (
                            prior_not_latest and detail_matches.get(NEW) is True),
                        "detail_date_matches_by_notice": detail_matches})
    # A search-index excerpt is not a directly inspected page. Its apparent
    # stage confusion is a separate hypothesis, never part of page counts.
    indexed = evidence.get("indexed_only")
    if (not isinstance(indexed, dict) or indexed.get("provider") != "Tenderwize"
            or indexed.get("url") != INDEX_URL
            or indexed.get("notice_id") != OLD or indexed.get("access") != "search_index_only"):
        raise ValueError("indexed observation must remain separate")
    indexed_day = _day(indexed.get("displayed_deadline_date"))
    mirrors = evidence.get("additional_information_date_mirrors")
    if not isinstance(mirrors, list) or len(mirrors) != 2:
        raise ValueError("two attributed mirror observations required")
    mirror_providers = set()
    mirror_dates = []
    for row in mirrors:
        if not isinstance(row, dict):
            raise ValueError("invalid mirror observation")
        provider = row.get("provider")
        if (provider not in {"Evergabe", "OpenProcurements"} or provider in mirror_providers
                or row.get("url") != PAGES[provider][0] or row.get("notice_id") != OLD
                or row.get("field") != "additional_information_deadline_BT-13"):
            raise ValueError("unbound additional-information mirror")
        mirror_providers.add(provider)
        mirror_dates.append(_day(row.get("displayed_calendar_date")))
    grouped = [r for r in results if r["scope"] == "procedure"]
    versioned = [r for r in results if r["scope"] == "notice"]
    return {"retrieved_on": observed.isoformat(), "selected_rendered_pages": len(results),
            "procedure_pages": len(grouped),
            "procedure_headlines_matching_latest": sum(r["headline_matches_comparison_notice"] for r in grouped),
            "procedure_headlines_matching_prior_not_latest": sum(r["procedure_headline_matches_prior_not_latest"] for r in grouped),
            "same_page_prior_headline_latest_detail_conflicts": sum(r["same_page_prior_headline_latest_detail_conflict"] for r in grouped),
            "notice_specific_pages": len(versioned),
            "notice_specific_headlines_matching_own_version": sum(r["headline_matches_comparison_notice"] for r in versioned),
            "indexed_only_observations": 1,
            "indexed_date_matches_two_additional_information_mirrors_not_tender": (
                all(d == indexed_day for d in mirror_dates) and indexed_day not in days[OLD]),
            "portal_access": "login_required", "operative_deadline_verified": False,
            "verified_legal_deadline_errors": None, "verified_supplier_savings": None,
            "verified_agentmine_revenue": None, "market_prevalence": None,
            "rows": results,
            "warning": "Selected rendered pages may be cached; retrieval is not live-page freshness. Historical notice pages are compared to their own version. The indexed-only date is a possible stage mix-up, not a directly verified page or official BT-13 extraction. No legal deadline, supplier harm, savings, market prevalence or payment inference."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chronology", type=Path, default=Path(CHRONOLOGY))
    parser.add_argument("--evidence", type=Path, default=Path(EVIDENCE))
    args = parser.parse_args(argv)
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    print(json.dumps(audit(load(args.chronology), load(args.evidence)), indent=2))


if __name__ == "__main__":
    main()
