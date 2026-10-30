"""Reconcile dated, overlapping primary-source reviews of a frozen TED cohort.

This is a coverage ledger, not a legal-deadline audit, market-prevalence
estimator, buyer-demand signal or supplier-outcome measurement. Offline only.
"""
from datetime import date, datetime

_COHORT = "predeclared_official_TED_competition_notice_cohort_not_unique_procedures_or_buyer_demand"
_PRIMARY = "fixed20_primary_portal_stage_observations"
_DATES = "fixed20_original_vs_directory_date_display"


def _notice(number):
    if (not isinstance(number, str) or not number.endswith("-2026") or
            not number[:-5].isascii() or not number[:-5].isdigit() or
            not (1 <= len(number[:-5]) <= 8)):
        raise ValueError("invalid notice ID")
    return number


def _official_url(number, url):
    if url != f"https://ted.europa.eu/sv/notice/{number}/html":
        raise ValueError("original URL not bound to notice")


def _unique_rows(rows, key, expected_ids):
    if not isinstance(rows, list):
        raise ValueError("expected list of rows")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid row")
        number = _notice(row.get(key))
        if number not in expected_ids or number in seen:
            raise ValueError("unknown or repeated cohort notice")
        seen.add(number)
    return seen


def summarize(cohort, primary, date_checks):
    """Count *unique* inspected originals, preserving missing access separately."""
    if not all(isinstance(x, dict) for x in (cohort, primary, date_checks)):
        raise ValueError("expected three evidence mappings")
    if (cohort.get("evidence_type") != _COHORT or
            primary.get("evidence_type") != _PRIMARY or
            date_checks.get("evidence_type") != _DATES):
        raise ValueError("wrong evidence types")
    expected_path = "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json"
    if primary.get("cohort_path") != expected_path or date_checks.get("cohort_path") != expected_path:
        raise ValueError("review references another cohort")
    cohort_rows = cohort.get("notice_items")
    if not isinstance(cohort_rows, list) or len(cohort_rows) != cohort.get("cohort_size") or not cohort_rows:
        raise ValueError("cohort size mismatch")
    expected = _unique_rows(cohort_rows, "publication_number", {_notice(x.get("publication_number")) for x in cohort_rows if isinstance(x, dict)})
    if len(expected) != len(cohort_rows):
        raise ValueError("duplicate cohort ID")
    old = set()
    for row in cohort_rows:
        if type(row.get("original_notice_checked")) is not bool:
            raise ValueError("invalid original review flag")
        if row["original_notice_checked"]:
            old.add(row["publication_number"])
    if old:
        reviewed = cohort.get("reviewed_first_record")
        if not isinstance(reviewed, dict) or reviewed.get("publication_number") not in old:
            raise ValueError("old original review has no source reference")
        _official_url(reviewed["publication_number"], reviewed.get("original_notice_url"))
        if len(old) != 1:
            raise ValueError("cohort fixture only documents one original review")
    primaries = primary.get("observations")
    primary_ids = _unique_rows(primaries, "publication_number", expected)
    portal_ids = set()
    for row in primaries:
        number = row["publication_number"]
        _official_url(number, row.get("official_notice_url"))
        if not isinstance(row.get("official_deadline_raw"), str) or not row["official_deadline_raw"]:
            raise ValueError("primary original missing deadline evidence")
        if row.get("portal_status") == "public_stage_and_date_text":
            if row.get("portal_stage") != row.get("official_stage") or not row.get("portal_deadline_raw"):
                raise ValueError("portal stage/date not corroborated")
            portal_ids.add(number)
        elif row.get("portal_status") != "not_observed_tool_access":
            raise ValueError("unrecognized portal evidence status")
    attempts = date_checks.get("attempts")
    _unique_rows(attempts, "publication_number", expected)
    date_observed, date_inaccessible = set(), set()
    for row in attempts:
        number = row["publication_number"]
        if row.get("status") == "observed":
            _official_url(number, row.get("official_notice_url"))
            try:
                instant = datetime.fromisoformat(row["official_original_datetime"])
                if instant.utcoffset() is None:
                    raise ValueError("naive original timestamp")
                date.fromisoformat(row["directory_display_date"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("invalid dated original/directory evidence") from exc
            date_observed.add(number)
        elif row.get("status") == "inaccessible":
            if not isinstance(row.get("reason"), str) or not row["reason"]:
                raise ValueError("inaccessible original needs reason")
            date_inaccessible.add(number)
        else:
            raise ValueError("unknown attempt status")
    originals = old | primary_ids | date_observed
    if date_inaccessible & originals:
        raise ValueError("inaccessible attempt conflicts with observed original")
    return {
        "frozen_cohort_notices": len(expected),
        "unique_originals_inspected": len(originals),
        "unique_original_notice_ids": sorted(originals),
        "originals_not_yet_inspected": len(expected - originals),
        "public_primary_portal_stage_date_corroborated": len(portal_ids),
        "unique_public_portal_ids": sorted(portal_ids),
        "explicit_inaccessible_attempts_in_latest_date_check": len(date_inaccessible),
        "latest_date_check_inaccessible_ids": sorted(date_inaccessible),
        "legally_operative_deadlines_verified": None,
        "supplier_savings_measured": None,
        "buyer_price_or_pilot_responses": None,
        "agentmine_paying_customers": None,
        "warning": "Unique coverage of three dated evidence files only; stale original_notice_checked flags in the frozen selection file are not current progress. No legal-deadline, prevalence, supplier-benefit or payment conclusion.",
    }
