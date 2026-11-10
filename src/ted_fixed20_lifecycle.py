"""Read-only TED Search API lifecycle metadata for the frozen 20-notice cohort.

Search projections are not original XML/PDF, complete legal amendment chains,
lot-level joins, paid supplier outcomes, or realized contract spend.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import UUID

from src.ted_notice_evidence import ENDPOINT, FIELDS, collect, post_json, summarize

COHORT_PATH = "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json"
PROJECTION = FIELDS + [
    "procedure-identifier", "notice-identifier", "notice-version", "form-type",
    "change-notice-version-identifier", "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot", "deadline-receipt-request-date-lot",
    "deadline-receipt-request-time-lot", "estimated-value-proc", "estimated-value-cur-proc",
    "framework-value-notice", "framework-value-cur-notice", "framework-approximate-value-notice",
    "framework-approximate-value-cur-notice", "result-value-notice", "result-value-cur-notice",
    "framework-estimated-value", "framework-estimated-value-cur", "result-lot-identifier",
    "winner-selection-status", "received-submissions-type-code", "received-submissions-type-val",
]


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,8}-20[0-9]{2}", value):
        raise ValueError("invalid publication number")
    number, year = value.split("-")
    if not int(number):
        raise ValueError("zero publication number")
    return f"{int(number)}-{year}"


def _single(value):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) and value else None


def _procedure(value):
    value = _single(value)
    if value is None:
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return str(parsed) if str(parsed) == value.lower() else None


def _query(field, values):
    if not values:
        raise ValueError("empty query")
    return f"{field} IN ({' '.join(values)})"


def _all_versions(query, fetch_page):
    def fetch(body):
        # The generic discovery collector intentionally defaults to latest
        # versions. A lifecycle audit must request historical versions too.
        return fetch_page({**body, "onlyLatestVersions": False})
    snapshot = collect(query, fetch_page=fetch, fields=PROJECTION, max_pages=3, limit=100)
    summarize(snapshot)
    if not snapshot["complete"]:
        raise ValueError("incomplete TED query; do not infer absent notices")
    rows = []
    seen = set()
    for raw in snapshot["notices"]:
        number = _id(raw["publication-number"])
        if number in seen:
            raise ValueError("duplicate canonical publication number")
        seen.add(number)
        # Keep published field names and raw scalar/array values. Never zip
        # parallel arrays or copy contact fields/format links into evidence.
        row = {key: raw[key] for key in PROJECTION if key in raw}
        row["publication-number"] = number
        rows.append(row)
    return {"query": query, "observed_at": snapshot["observed_at"],
            "reported_total_notices": snapshot["reported_total_notices"],
            "pages_fetched": snapshot["pages_fetched"], "complete_for_query": True,
            "only_latest_versions": False, "notices": rows}


def review(cohort, *, fetch_page=post_json):
    if (not isinstance(cohort, dict) or cohort.get("complete_frame_reconciled") is not True
            or cohort.get("cohort_size") != 20 or not isinstance(cohort.get("notice_items"), list)
            or len(cohort["notice_items"]) != 20):
        raise ValueError("frozen reconciled 20-notice cohort required")
    ids = [_id(row["publication_number"]) for row in cohort["notice_items"]]
    if len(set(ids)) != 20:
        raise ValueError("duplicate frozen cohort ID")
    original_query = _all_versions(_query("publication-number", ids), fetch_page)
    originals = {row["publication-number"]: row for row in original_query["notices"]}
    if not set(originals).issubset(ids):
        raise ValueError("unexpected publication outside frozen cohort")
    mapping = {number: _procedure(row.get("procedure-identifier")) for number, row in originals.items()}
    procedures = sorted({value for value in mapping.values() if value})
    lifecycle = _all_versions(_query("procedure-identifier", procedures), fetch_page) if procedures else None
    groups = {procedure: [] for procedure in procedures}
    if lifecycle:
        for row in lifecycle["notices"]:
            procedure = _procedure(row.get("procedure-identifier"))
            if procedure not in groups:
                raise ValueError("lifecycle notice not bound to queried procedure")
            groups[procedure].append(row)
    # A complete search result is not enough if the same frozen publication
    # disappeared or changed between the two query snapshots.
    lifecycle_by_id = {row["publication-number"]: row for rows in groups.values() for row in rows}
    bound_ids = [number for number, procedure in mapping.items() if procedure]
    if any(lifecycle_by_id.get(number) != originals[number] for number in bound_ids):
        raise ValueError("frozen notice missing or changed between TED queries")
    histories = []
    for procedure, rows in groups.items():
        original_ids = sorted(number for number, value in mapping.items() if value == procedure)
        result_ids = [r["publication-number"] for r in rows if
                      _single(r.get("form-type")) == "result" or
                      (_single(r.get("notice-type")) or "").startswith("can-")]
        change_ids = [r["publication-number"] for r in rows if r.get("change-notice-version-identifier")]
        histories.append({"procedure_identifier": procedure, "frozen_notice_ids": original_ids,
                          "returned_notice_ids": sorted(r["publication-number"] for r in rows),
                          "frozen_ids_present_in_lifecycle": sorted(set(original_ids) &
                              {r["publication-number"] for r in rows}),
                          "result_notice_ids": sorted(result_ids), "change_reference_notice_ids": sorted(change_ids)})
    return {"evidence_type": "frozen_TED20_search_metadata_lifecycle_not_original_or_legal_clearance",
            "source_url": ENDPOINT, "observed_at": datetime.now(timezone.utc).isoformat(),
            "cohort_path": COHORT_PATH, "cohort_size": 20, "projection": PROJECTION,
            "original_id_query": original_query, "procedure_query": lifecycle,
            "frozen_ids_with_metadata": len(originals), "missing_frozen_ids": sorted(set(ids)-set(originals)),
            "frozen_ids_without_procedure": sorted(number for number in ids if not mapping.get(number)),
            "distinct_procedure_ids": len(procedures), "procedure_histories": histories,
            "frozen_rows_identical_across_queries": len(bound_ids),
            "frozen_change_reference_ids": sorted(number for number, row in originals.items()
                                                   if row.get("change-notice-version-identifier")),
            "frozen_nonfirst_version_ids": sorted(number for number, row in originals.items()
                if str(row.get("notice-version", "")).isdigit() and int(row["notice-version"]) > 1),
            "procedures_with_result_metadata": sum(bool(h["result_notice_ids"]) for h in histories),
            "procedures_with_change_reference_metadata": sum(bool(h["change_reference_notice_ids"]) for h in histories),
            "new_original_xml_pdf_reviews": 0, "new_portal_checks": 0, "amendment_histories_cleared": 0,
            "verified_legal_deadline_errors": None, "verified_supplier_payments": None,
            "verified_agentmine_revenue": None,
            "warning": "Search API metadata only. Complete means returned query population, not legal completeness. Repeated fields are unjoined; result values and framework limits are not realized spend."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, default=Path(COHORT_PATH))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = review(json.loads(args.cohort.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in
                      {"original_id_query", "procedure_query", "projection", "procedure_histories"}}, indent=2))


if __name__ == "__main__":
    main()
