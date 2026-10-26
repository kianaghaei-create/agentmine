"""Read-only official TED Search API projection for a fixed 20-notice cohort.

Not original XML, submission portal, amendments, verified deadlines, or buyers.
Preserves raw official field values and explicit coverage instead of guessing
lot/deadline semantics from flattened API representations.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.ted_notice_evidence import FIELDS, collect, post_json

EXTRA_FIELDS = [
    "main-classification-proc",
    "main-classification-lot",
    "additional-classification-proc",
    "procedure-identifier",
    "previous-notice-id-proc",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "deadline-receipt-request-date-lot",
    "deadline-receipt-request-time-lot",
    "submission-url-lot",
]
PROJECTION = FIELDS + EXTRA_FIELDS


def project_cohort(cohort, *, fetch_page=post_json, observed_at=None):
    if not isinstance(cohort, dict) or cohort.get("complete_frame_reconciled") is not True:
        raise ValueError("predeclared reconciled cohort required")
    query = cohort.get("query")
    items = cohort.get("notice_items")
    if not isinstance(query, str) or not query.strip() or not isinstance(items, list) or len(items) != 20 or cohort.get("cohort_size") != 20:
        raise ValueError("exact 20-item query-defined cohort required")
    ids = [r.get("publication_number") if isinstance(r, dict) else None for r in items]
    if any(not isinstance(v, str) or not v.strip() for v in ids) or len(set(ids)) != 20:
        raise ValueError("invalid or duplicate cohort IDs")
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    snapshot = collect(query, fetch_page=fetch_page, fields=PROJECTION, max_pages=4,
                       limit=50, observed_at=observed_at)
    if not snapshot["complete"] or snapshot["unique_notices_collected"] != snapshot["reported_total_notices"]:
        raise ValueError("incomplete official TED search projection")
    by_id = {r["publication-number"]: r for r in snapshot["notices"]}
    results = []
    for number in ids:
        row = by_id.get(number)
        results.append({
            "publication_number": number,
            "status": "official_search_api_projection_available" if row is not None else "missing_from_new_official_query_frame",
            "official_search_fields": {field: row.get(field) for field in PROJECTION} if row is not None else None,
            "original_notice_xml_parsed": False,
            "amendments_verified": False,
            "submission_portal_verified": False,
            "legal_deadline_verified": False,
        })
    present = {field: sum(row["official_search_fields"] is not None
                          and row["official_search_fields"].get(field) not in (None, "", [], {})
                          for row in results) for field in PROJECTION}
    frame_hash = hashlib.sha256(json.dumps(snapshot["notices"], sort_keys=True,
                                           ensure_ascii=False).encode("utf-8")).hexdigest()
    found = sum(row["official_search_fields"] is not None for row in results)
    return {
        "evidence_type": "official_TED_search_API_projection_not_original_XML_or_legal_deadlines",
        "source_url": snapshot["source_url"],
        "observed_at": snapshot["observed_at"],
        "query": query,
        "selection_rule": cohort.get("selection_rule"),
        "cohort_notice_count": 20,
        "current_query_frame_count": snapshot["reported_total_notices"],
        "initial_query_frame_count": cohort.get("complete_query_frame_notices"),
        "frame_count_changed": snapshot["reported_total_notices"] != cohort.get("complete_query_frame_notices"),
        "complete_current_query_frame": True,
        "full_current_query_frame_sha256": frame_hash,
        "projected_cohort_notice_count": found,
        "missing_cohort_notice_count": 20 - found,
        "field_nonempty_coverage_in_fixed_20": present,
        "verified_supplier_savings": None,
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue": None,
        "items": results,
        "warning": "Official TED Search API fields, not original XML or verified current portal/amendment status. Raw lot fields are not legal deadline advice. Notice counts are not unique procedures or paying customers.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    result = project_cohort(cohort)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"items", "field_nonempty_coverage_in_fixed_20"}}, indent=2))


if __name__ == "__main__":
    main()
