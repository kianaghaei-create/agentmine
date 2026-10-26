"""Fail-closed primary-portal stage audit for a predeclared 20-notice TED cohort.

A public portal's displayed date is not proof of the operative legal deadline.
This audit records source-backed stage/date visibility, not supplier outcomes.
"""
from collections import Counter
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

_FIELD = {
    "deadline-receipt-request-date-lot": "participation_request",
    "deadline-receipt-tender-date-lot": "tender",
}
_PORTAL_HOSTS = {"www.kommersannons.se", "kommersannons.se", "annonser.clira.io"}
_STATUSES = {"public_stage_and_date_text", "not_observed_tool_access"}


def _rows(rows, *, count, label):
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError(f"{label}: expected {count} rows")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("publication_number"), str):
            raise ValueError(f"{label}: invalid row")
        number = row["publication_number"]
        if not number.endswith("-2026") or number in out:
            raise ValueError(f"{label}: duplicate or invalid publication number")
        out[number] = row
    return out


def _url(url, host, number=None):
    if not isinstance(url, str):
        raise ValueError("source URL missing")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in host or parsed.username
            or parsed.password or parsed.fragment or not parsed.path):
        raise ValueError("untrusted source URL")
    if number and number not in parsed.path:
        raise ValueError("source URL not bound to publication number")


def audit(cohort, official, directory, primary):
    """Return a fixed-denominator descriptive audit; never infer legal errors."""
    if (cohort.get("complete_frame_reconciled") is not True or cohort.get("cohort_size") != 20
            or official.get("complete_current_query_frame") is not True
            or official.get("missing_cohort_count") != 0
            or official.get("query") != cohort.get("query")):
        raise ValueError("incomplete or nonmatching official cohort")
    fixed = _rows(cohort.get("notice_items"), count=20, label="cohort")
    projected = _rows(official.get("rows"), count=20, label="official")
    displayed = _rows(directory.get("directory_display_observations"), count=20, label="directory")
    if set(fixed) != set(projected) or set(fixed) != set(displayed):
        raise ValueError("fixed cohort IDs do not reconcile")
    if directory.get("official_projection_observed_at_utc") != official.get("observed_at_utc"):
        raise ValueError("directory evidence does not bind to official projection")
    if primary.get("evidence_type") != "fixed20_primary_portal_stage_observations":
        raise ValueError("unsupported primary evidence")
    try:
        observed_on = date.fromisoformat(primary["observed_on_utc_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid observation date") from exc
    if observed_on > datetime.now(timezone.utc).date():
        raise ValueError("future observation")
    rows = primary.get("observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("primary evidence requires observations")
    observations = _rows(rows, count=len(rows), label="primary")
    if not set(observations) <= set(fixed):
        raise ValueError("primary observations outside fixed cohort")
    counts = Counter()
    results = []
    for number in fixed:
        expected = _FIELD.get(projected[number].get("field_kind"))
        if expected is None:
            raise ValueError("unsupported official projection stage")
        directory_row = displayed[number]
        if directory_row.get("source_url") != f"https://upphandla.app/en/tender/{number}":
            raise ValueError("unbound directory source")
        status = directory_row.get("display_status")
        if status not in {"date_displayed", "no_deadline_displayed", "page_unavailable"}:
            raise ValueError("invalid directory status")
        state = "original_not_reviewed"
        item = {"publication_number": number, "status": state, "operative_deadline_verified": False}
        if number in observations:
            row = observations[number]
            _url(row.get("official_notice_url"), {"ted.europa.eu"}, number)
            if row["official_notice_url"] != f"https://ted.europa.eu/sv/notice/{number}/html":
                raise ValueError("unexpected original notice URL")
            original_stage = row.get("official_stage")
            if original_stage not in {"participation_request", "tender"}:
                raise ValueError("invalid original stage")
            try:
                original_date = date.fromisoformat(row["official_deadline_date"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("invalid original deadline date") from exc
            if not isinstance(row.get("official_deadline_raw"), str) or not row["official_deadline_raw"].strip():
                raise ValueError("original deadline text missing")
            if row.get("amendments_status") != "not_checked":
                raise ValueError("unverified amendment status must not claim clearance")
            _url(row.get("portal_url"), _PORTAL_HOSTS)
            portal_status = row.get("portal_status")
            if portal_status not in _STATUSES:
                raise ValueError("invalid portal status")
            if original_stage != expected:
                state = "original_projection_stage_conflict"
            elif portal_status == "not_observed_tool_access":
                if "portal_stage" in row or "portal_deadline_raw" in row:
                    raise ValueError("inaccessible portal cannot supply observations")
                state = "original_observed_portal_unverified"
            else:
                if row.get("portal_stage") not in {"participation_request", "tender"}:
                    raise ValueError("portal stage missing")
                if not isinstance(row.get("portal_deadline_raw"), str) or not row["portal_deadline_raw"].strip():
                    raise ValueError("portal deadline text missing")
                if row.get("portal_date_interpretation") != "unverified_locale":
                    raise ValueError("do not silently parse ambiguous portal date")
                if row["portal_stage"] != original_stage:
                    state = "primary_stage_conflict_unresolved"
                elif status == "no_deadline_displayed":
                    state = "primary_stage_agrees_directory_no_date"
                else:
                    state = "primary_stage_agrees_no_directory_omission_shown"
            item.update({"status": state, "official_original_date": original_date.isoformat(),
                         "original_stage": original_stage, "portal_status": portal_status,
                         "amendments_checked": False})
        counts[state] += 1
        results.append(item)
    return {
        "evidence_type": "fixed20_primary_stage_visibility_not_operative_deadline",
        "observed_on_utc_date": observed_on.isoformat(),
        "fixed_cohort_count": 20,
        "original_notice_observed_count": 20 - counts["original_not_reviewed"],
        "public_portal_stage_agrees_directory_no_date_count": counts["primary_stage_agrees_directory_no_date"],
        "public_portal_stage_conflicts_count": counts["primary_stage_conflict_unresolved"],
        "primary_portal_unverified_count": counts["original_not_reviewed"] + counts["original_observed_portal_unverified"],
        "amendments_checked_count": 0,
        "verified_operative_deadline_errors": 0,
        "verified_supplier_savings": None,
        "verified_paying_customers": None,
        "status_counts": dict(sorted(counts.items())),
        "items": results,
        "warning": "Source texts are public observations; portal date locale, amendments, current legal deadline, customer value and payment intent remain unverified. Fixed denominator 20; do not report a population error rate."
    }
