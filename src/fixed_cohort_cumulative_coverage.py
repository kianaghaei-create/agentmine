"""Reconcile *all* dated primary-original reviews of the frozen TED-20.

Read-only provenance bookkeeping, not a deadline/legal-error audit, random
prevalence estimate, supplier-outcome measure or demand signal. The older
three-fixture coverage summary is deliberately a *partial* view.
"""
from datetime import date, datetime, timezone
import re
from urllib.parse import parse_qs, urlsplit

from src.fixed_cohort_coverage import summarize as partial_summary, _official_url, _notice

COHORT_PATH = "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json"


def _rows(obj, field, expected_type):
    if not isinstance(obj, dict) or obj.get("evidence_type") != expected_type:
        raise ValueError("unexpected evidence type")
    rows = obj.get(field)
    if not isinstance(rows, list):
        raise ValueError("missing source rows")
    return rows


def _bound(number, url, ids, *, pdf=False):
    number = _notice(number)
    if number not in ids:
        raise ValueError("source outside frozen cohort")
    if pdf:
        if url != f"https://ted.europa.eu/en/notice/{number}/pdf":
            raise ValueError("PDF original URL not bound to notice")
    else:
        _official_url(number, url)
    return number


def _offset_datetime(raw):
    if not isinstance(raw, str):
        raise ValueError("missing original timestamp")
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid original timestamp") from exc
    if stamp.utcoffset() is None:
        raise ValueError("original timestamp must be timezone-aware")
    return stamp


def summarize_cumulative(cohort, primary, dates, three, four, portal, option, pdf, pdf_new=None):
    """Union dated evidence stages; optional ninth PDF preserves old callers."""
    base = partial_summary(cohort, primary, dates)
    ids = {row["publication_number"] for row in cohort["notice_items"]}
    if (three.get("fixed_cohort_source") != COHORT_PATH or
            four.get("fixed_cohort_path") != COHORT_PATH or
            portal.get("cohort_source") != COHORT_PATH or
            option.get("fixed20_denominator") != len(ids) or
            pdf.get("fixed_cohort_denominator") != len(ids)):
        raise ValueError("source not bound to frozen cohort")
    originals = set(base["unique_original_notice_ids"])

    for obj, field, kind, url_field, timestamp_field in (
        (three, "new_notices", "fixed20_new_original_notice_stage_date_crosscheck",
         "official_notice_url", "official_deadline_local"),
        (four, "observations", "fixed20_four_official_original_vs_directory_date_stage_crosschecks",
         "official_notice_url", "official_deadline_local"),
    ):
        seen = set()
        for row in _rows(obj, field, kind):
            if not isinstance(row, dict):
                raise ValueError("invalid original observation")
            number = _bound(row.get("publication_number"), row.get(url_field), ids)
            if number in seen:
                raise ValueError("duplicate source observation")
            seen.add(number)
            _offset_datetime(row.get(timestamp_field))
        originals.update(seen)

    if portal.get("evidence_type") != (
            "predeclared_fixed20_official_original_and_public_primary_portal_reconciliation_not_legal_error_or_paid_demand"):
        raise ValueError("wrong portal evidence")
    p = portal.get("notice")
    if not isinstance(p, dict):
        raise ValueError("missing portal observation")
    portal_number = _bound(p.get("publication_number"), p.get("official_original_url"), ids)
    original_stamp = _offset_datetime(p.get("official_deadline_local"))
    # Do not promote a self-declared "portal date matches" boolean into
    # independent corroboration without a bound public portal and a
    # parseable date in the actual transcribed portal text. This one
    # dated evidence fixture uses Kommers' US month/day/year presentation.
    portal_url = p.get("public_buyer_submission_portal_url")
    portal_text = p.get("public_portal_observed")
    if not isinstance(portal_url, str) or not isinstance(portal_text, str):
        raise ValueError("public portal provenance missing")
    parsed = urlsplit(portal_url)
    if (parsed.scheme != "https" or parsed.netloc != "www.kommersannons.se"
            or parsed.path != "/eLite/Notice/NoticeOverview.aspx"
            or parsed.fragment or
            not re.fullmatch(r"[1-9][0-9]*",
                             parse_qs(parsed.query).get("ProcurementId", [""])[0])
            or set(parse_qs(parsed.query)) != {"ProcurementId"}):
        raise ValueError("public portal source URL invalid")
    match = re.search(r"\\bFinal day for submitting\\s+([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})\\b",
                      portal_text)
    if not match:
        raise ValueError("public portal date text missing")
    try:
        month, day, year = map(int, match.groups())
        portal_day = date(year, month, day)
    except ValueError as exc:
        raise ValueError("public portal date invalid") from exc
    frozen_date = next(row["publication_date"] for row in cohort["notice_items"]
                       if row["publication_number"] == portal_number)
    if (portal_day != original_stamp.date() or
            p.get("official_notice_version") != "01" or
            p.get("official_publication_date") != frozen_date):
        raise ValueError("portal date or original provenance inconsistent")
    if (p.get("public_portal_stage") != p.get("official_deadline_stage") or
            p.get("portal_date_matches_official_original_local_day") is not True or
            not isinstance(p.get("public_portal_observed"), str) or
            not p["public_portal_observed"].strip() or
            original_stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") != p.get("official_deadline_utc")):
        raise ValueError("portal stage/date corroboration unsupported")
    originals.add(portal_number)

    audit = option.get("audit_input")
    if not isinstance(audit, dict) or audit.get("evidence_type") != "public_original_vs_directory_option_claim":
        raise ValueError("wrong option evidence")
    option_number = _bound(audit.get("publication_number"), audit.get("official_url"), ids)
    if (audit.get("amendments_verified") is not False or
            option.get("original_notice_observations", {}).get("original_notice_version") != "01"):
        raise ValueError("unsupported option original")
    originals.add(option_number)

    if pdf.get("evidence_type") != "predeclared_fixed20_direct_official_TED_PDF_original_not_operative_legal_deadline":
        raise ValueError("wrong PDF evidence")
    source = pdf.get("official_source")
    if not isinstance(source, dict):
        raise ValueError("missing PDF original")
    pdf_number = _bound(pdf.get("publication_number"), source.get("url"), ids, pdf=True)
    if source.get("original_notice_directly_verified") is not True:
        raise ValueError("PDF original not verified")
    pdf_stamp = _offset_datetime(source.get("deadline_local"))
    if pdf_stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") != source.get("deadline_utc"):
        raise ValueError("PDF UTC conversion mismatch")
    originals.add(pdf_number)

    # Ninth source is a newly accessible original PDF, not a portal or legal
    # deadline confirmation. The historical eight-input call stays valid.
    if pdf_new is not None:
        if (not isinstance(pdf_new, dict) or
                pdf_new.get("evidence_type") !=
                "predeclared_fixed20_direct_official_TED_PDF_original_not_operative_legal_deadline" or
                pdf_new.get("fixed_cohort_denominator") != len(ids)):
            raise ValueError("wrong additional PDF cohort evidence")
        new_source = pdf_new.get("official_source")
        if not isinstance(new_source, dict):
            raise ValueError("missing additional PDF source")
        new_number = _bound(pdf_new.get("publication_number"), new_source.get("url"), ids, pdf=True)
        if new_number == pdf_number:
            raise ValueError("duplicate PDF original source")
        frozen_date = next(row["publication_date"] for row in cohort["notice_items"]
                           if row["publication_number"] == new_number)
        if (new_source.get("original_notice_directly_verified") is not True or
                new_source.get("notice_version") != "01" or
                new_source.get("notice_publication_date") != frozen_date):
            raise ValueError("additional original PDF unverified or publication mismatch")
        new_stamp = _offset_datetime(new_source.get("deadline_local"))
        if (new_stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                != new_source.get("deadline_utc")):
            raise ValueError("additional PDF UTC conversion mismatch")
        originals.add(new_number)

    # An original HTML retrieval may fail on a later date while an earlier
    # direct official PDF was independently inspected. Both facts can coexist.
    inaccessible = set(base["latest_date_check_inaccessible_ids"])
    corroborated = set(base["unique_public_portal_ids"]) | {portal_number}
    if not originals <= ids or not corroborated <= originals:
        raise ValueError("invalid coverage union")
    return {
        "frozen_cohort_notices": len(ids),
        "unique_originals_inspected": len(originals),
        "unique_original_notice_ids": sorted(originals),
        "originals_not_yet_inspected": len(ids - originals),
        "not_yet_inspected_ids": sorted(ids - originals),
        "public_primary_portal_stage_date_corroborated": len(corroborated),
        "unique_public_portal_ids": sorted(corroborated),
        "latest_date_check_inaccessible_attempts": len(inaccessible),
        "latest_date_check_inaccessible_but_elsewhere_verified_ids": sorted(inaccessible & originals),
        "latest_date_check_inaccessible_and_still_unverified_ids": sorted(inaccessible - originals),
        "amendment_histories_cleared": 0,
        "legally_operative_deadlines_verified": None,
        "actual_paired_supplier_tasks": 0,
        "actual_supplier_time_saved_minutes": None,
        "explicit_price_or_pilot_responses": 0,
        "verified_agentmine_paying_customers": None,
        "verified_agentmine_revenue": None,
        "warning": "Deduplicated original-review coverage of eight dated fixtures, not a legal deadline, random mismatch prevalence, verified customer outcome or paid demand. Portal stage/date text does not clear amendments or exact operative cutoffs.",
    }
