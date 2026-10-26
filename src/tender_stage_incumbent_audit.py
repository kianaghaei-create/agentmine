"""Audit a fixed official TED cohort against observed public directory UI fields.

This is a *visibility* audit, not legal deadline verification, subscriber demand,
proof of current buyer intent, or a representative market prevalence estimate.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re

_ID = re.compile(r"^[1-9][0-9]{0,7}-20[0-9]{2}$")
_DATE = re.compile(r"^\\d{4}-\\d{2}-\\d{2}$")
_FIELD_STAGE = {
    "deadline-receipt-tender-date-lot": "tender",
    "deadline-receipt-request-date-lot": "participation_request",
}
_DISPLAY = {"date_displayed", "no_deadline_displayed", "page_unavailable"}
_COMPARE = {"participation_date_displayed", "tender_date_displayed", "no_deadline_displayed"}


def _valid_date(value):
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("displayed_date must be an ISO calendar date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid displayed_date") from exc


def _unique_by_id(rows, *, expected, label):
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError(f"{label} requires exactly {expected} rows")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} row must be an object")
        number = row.get("publication_number")
        if not isinstance(number, str) or not _ID.fullmatch(number) or number in out:
            raise ValueError(f"{label} invalid or duplicate publication number")
        out[number] = row
    return out


def audit(cohort, official, evidence):
    if not isinstance(cohort, dict) or cohort.get("complete_frame_reconciled") is not True or cohort.get("cohort_size") != 20:
        raise ValueError("complete predeclared cohort required")
    fixed = _unique_by_id(cohort.get("notice_items"), expected=20, label="cohort")
    if not isinstance(official, dict) or official.get("complete_current_query_frame") is not True or official.get("projected_cohort_count") != 20 or official.get("missing_cohort_count") != 0:
        raise ValueError("complete official projection required")
    official_rows = _unique_by_id(official.get("rows"), expected=20, label="official")
    if set(official_rows) != set(fixed) or official.get("query") != cohort.get("query"):
        raise ValueError("official projection must match fixed cohort and query")
    if not isinstance(evidence, dict) or evidence.get("official_projection_path") != "data/evidence/ted_cpv72_search_projection_summary_2026-10-26.json":
        raise ValueError("expected source-attributed directory evidence")
    if evidence.get("official_projection_observed_at_utc") != official.get("observed_at_utc"):
        raise ValueError("official projection observation timestamp mismatch")
    displays = _unique_by_id(evidence.get("directory_display_observations"), expected=20, label="directory")
    if set(displays) != set(fixed):
        raise ValueError("directory rows must cover every predeclared ID")

    counts = Counter()
    items = []
    for number in fixed:
        official_row, display = official_rows[number], displays[number]
        stage = _FIELD_STAGE.get(official_row.get("field_kind"))
        if stage is None:
            raise ValueError("unknown or ambiguous official stage field")
        status = display.get("display_status")
        if status not in _DISPLAY or display.get("source_url") != f"https://upphandla.app/en/tender/{number}":
            raise ValueError("invalid or unbound public directory observation")
        if status == "date_displayed":
            _valid_date(display.get("displayed_date"))
        elif "displayed_date" in display:
            raise ValueError("missing/unavailable deadline must not carry a date")
        counts[f"{stage}__{status}"] += 1
        items.append({"publication_number": number, "official_published_field_stage": stage,
                      "directory_display_status": status,
                      "directory_displayed_date": display.get("displayed_date"),
                      "directory_source_url": display["source_url"],
                      "operative_deadline_verified": False})

    comparators = evidence.get("independent_competitor_observations", [])
    if not isinstance(comparators, list):
        raise ValueError("invalid comparator observations")
    comparator_ids = set()
    for row in comparators:
        if not isinstance(row, dict):
            raise ValueError("invalid comparator row")
        number = row.get("publication_number")
        if number not in fixed or number in comparator_ids:
            raise ValueError("invalid/duplicate comparator notice")
        comparator_ids.add(number)
        if row.get("source_url", "").startswith("https://tilldelat.se/upphandling/") is False:
            raise ValueError("comparator source must be public Tilldelat page")
        if row.get("display_status") not in _COMPARE:
            raise ValueError("invalid comparator status")
        if row["display_status"].endswith("_date_displayed"):
            _valid_date(row.get("displayed_date"))
        elif "displayed_date" in row:
            raise ValueError("no-deadline comparator cannot carry a date")
        if row["display_status"] == "participation_date_displayed" and _FIELD_STAGE.get(official_rows[number]["field_kind"]) != "participation_request":
            raise ValueError("comparator stage conflicts with official field type")
    request_total = sum(x["official_published_field_stage"] == "participation_request" for x in items)
    tender_total = 20 - request_total
    return {
        "evidence_type": "predeclared_directory_stage_visibility_not_legal_error_or_paid_demand",
        "observed_at_utc": evidence.get("observed_at_utc"),
        "fixed_cohort_count": 20,
        "public_directory_page_observed": 20 - counts["participation_request__page_unavailable"] - counts["tender__page_unavailable"],
        "public_directory_page_unavailable": counts["participation_request__page_unavailable"] + counts["tender__page_unavailable"],
        "official_participation_request_field_count": request_total,
        "official_tender_receipt_field_count": tender_total,
        "request_field_directory_no_deadline": counts["participation_request__no_deadline_displayed"],
        "request_field_directory_date_displayed": counts["participation_request__date_displayed"],
        "tender_field_directory_no_deadline": counts["tender__no_deadline_displayed"],
        "tender_field_directory_date_displayed": counts["tender__date_displayed"],
        "independent_competitor_stage_date_examples": len(comparator_ids),
        "legal_deadline_errors_verified": 0,
        "verified_supplier_savings": None,
        "verified_paying_customers": None,
        "verified_revenue": None,
        "items": items,
        "warning": "Fixed 20 notice UI audit; cached page freshness varies. Official search field presence is not an operative deadline. No portals/amendments verified; no market prevalence or customer value proven."
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--official", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = audit(load(args.cohort), load(args.official), load(args.evidence))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "items"}, indent=2))


if __name__ == "__main__":
    main()
