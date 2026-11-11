"""Bounded official result-notice research, not a live RFQ or lost-demand feed.

Predeclared population: October 2026 Swedish-buyer TED award/result notices
with any CPV 48/72. All published versions; report notice-level counts only.
A strict primary-IT subset uses the procedure's main CPV. Never join parallel
lot arrays, infer a current buying need, or sum estimated contract values.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re

from src.ted_notice_evidence import ENDPOINT, FIELDS, collect, post_json, summarize
from src.ted_fixed20_lifecycle import _id, _procedure, _single

QUERY = ("publication-date >= 20261001 AND publication-date <= 20261031 "
         "AND buyer-country = SWE AND (classification-cpv = 48* OR classification-cpv = 72*) "
         "AND notice-type IN (can-standard can-social can-desg)")
TYPES = {"can-standard", "can-social", "can-desg"}
PROJECTION = FIELDS + [
    "main-classification-proc", "procedure-identifier", "notice-version", "form-type",
    "identifier-lot", "result-lot-identifier", "winner-selection-status",
    "non-award-justification", "received-submissions-type-code",
    "received-submissions-type-val", "procurement-relaunch-proc",
    "procurement-relaunch", "estimated-value-proc", "estimated-value-cur-proc",
]
PUBLIC_FIELDS = [key for key in PROJECTION if key not in {"buyer-name", "notice-title"}]
REASONS = {"all-rej", "chan-need", "ins-fund", "no-rece", "no-signed",
           "one-admis", "other", "rev-body", "rev-buyer", "tch-pr-error"}
STATUSES = {"clos-nw", "open-nw", "selec-w"}


def _values(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _true(value):
    return value is True or value == "true" or value == ["true"] or value == [True]


def _tender_count(row):
    # Even one result lot can have several submission categories. Do not zip
    # independent arrays or interpret an electronic/SME count as total bids.
    if _values(row.get("received-submissions-type-code")) != ["tenders"]:
        return None
    values = _values(row.get("received-submissions-type-val"))
    if len(values) != 1:
        return None
    value = values[0]
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,12}", value):
        return int(value)
    return None


def classify(row):
    """Conservative single-result classification; no current demand inference."""
    number = _id(row["publication-number"])
    pub = _single(row.get("publication-date"))
    if (not pub or not re.fullmatch(r"2026-10-[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})?", pub)
            or not date(2026, 10, 1) <= date.fromisoformat(pub[:10]) <= date(2026, 10, 31)
            or _single(row.get("notice-type")) not in TYPES
            or _single(row.get("form-type")) != "result"
            or "SWE" not in _values(row.get("buyer-country"))
            or not any(isinstance(c, str) and re.fullmatch(r"(48|72)[0-9]{6}", c)
                       for c in _values(row.get("classification-cpv")))):
        raise ValueError("row outside predeclared result-notice frame")
    main = _single(row.get("main-classification-proc"))
    scope = ("primary_it" if main and re.fullmatch(r"(48|72)[0-9]{6}", main)
             else "other_main_cpv" if main and re.fullmatch(r"[0-9]{8}", main)
             else "main_cpv_unknown")
    lots = _values(row.get("result-lot-identifier"))
    declared = _values(row.get("identifier-lot"))
    status = _single(row.get("winner-selection-status"))
    reason = _single(row.get("non-award-justification"))
    single = len(lots) == 1 and isinstance(lots[0], str) and bool(re.fullmatch(r"LOT-[0-9]{4}", lots[0]))
    count = _tender_count(row) if single else None
    # A procedure-wide estimate is not a single-lot estimate unless the
    # declared lot and result lot are both uniquely and identically bound.
    one_declared = single and declared == lots
    relaunch_proc = _true(row.get("procurement-relaunch-proc"))
    relaunch_lot = one_declared and _true(row.get("procurement-relaunch"))
    if not single or status not in STATUSES:
        kind = "unjoined_or_unknown_result"
    elif status == "selec-w":
        kind = "winner_selected"
    elif status == "open-nw":
        kind = "competition_still_open"
    elif reason == "no-rece":
        kind = ("closed_no_submissions_count_zero" if count == 0 else
                "closed_no_submissions_reason_only" if count is None else
                "closed_no_submissions_count_conflict")
    elif reason in REASONS:
        kind = "closed_other_reason"
    else:
        kind = "closed_reason_unknown"
    return {"publication_number": number, "source_url": f"https://ted.europa.eu/en/notice/{number}/html",
            "procedure_identifier": _procedure(row.get("procedure-identifier")),
            "main_cpv_scope": scope, "main_cpv": main, "single_result_lot": single,
            "single_declared_lot_matches_result": one_declared,
            "result_lot": lots[0] if single else None, "result_status": status if single else None,
            "non_award_reason": reason if single and status == "clos-nw" and reason in REASONS else None,
            "total_tenders_reported": count, "classification": kind,
            "procedure_relaunch_reported_true": relaunch_proc,
            "single_declared_lot_relaunch_reported_true": relaunch_lot,
            "current_need_verified": None, "verified_agentmine_demand": None}


def review(snapshot):
    summarize(snapshot)
    if snapshot["query"] != QUERY or not snapshot["complete"]:
        raise ValueError("complete predeclared query required")
    rows, seen = [], set()
    for raw in snapshot["notices"]:
        result = classify(raw)
        if result["publication_number"] in seen:
            raise ValueError("duplicate canonical publication number")
        seen.add(result["publication_number"])
        rows.append(result)
    rows.sort(key=lambda r: int(r["publication_number"].split("-")[0]))
    primary = [r for r in rows if r["main_cpv_scope"] == "primary_it"]
    strict = [r for r in primary if r["classification"] == "closed_no_submissions_count_zero"]
    return {"evidence_type": "official_TED_result_notice_nonaward_research_not_live_Rfq",
            "source_url": ENDPOINT, "observed_at": snapshot["observed_at"], "query": QUERY,
            "only_latest_versions": False, "reported_total_notices": snapshot["reported_total_notices"],
            "pages_fetched": snapshot["pages_fetched"], "complete_for_query": True,
            "projection": PROJECTION, "notice_count": len(rows),
            "main_cpv_scope_counts": dict(Counter(r["main_cpv_scope"] for r in rows)),
            "primary_it_notice_count": len(primary),
            "primary_it_classification_counts": dict(Counter(r["classification"] for r in primary)),
            "primary_it_closed_reason_counts": dict(Counter(r["non_award_reason"] or "unknown"
                for r in primary if r["classification"].startswith("closed_"))),
            "primary_it_zero_tender_notice_ids": [r["publication_number"] for r in strict],
            "primary_it_zero_tender_with_relaunch_indicator_ids": [r["publication_number"] for r in strict
                if r["procedure_relaunch_reported_true"] or r["single_declared_lot_relaunch_reported_true"]],
            "primary_it_distinct_known_procedure_ids": len({r["procedure_identifier"] for r in primary
                if r["procedure_identifier"]}),
            "rows": rows,
            "public_projection_rows": [{key: raw[key] for key in PUBLIC_FIELDS if key in raw}
                                       for raw in snapshot["notices"]],
            "verified_live_unmet_needs": None, "verified_paying_customers": None,
            "verified_agentmine_revenue": None,
            "warning": "Publication-window notice counts, not unique tenders, lots, buyers or national prevalence. "
                       "No parallel array joins; closed/no submissions is a historical reported result, not an open RFQ. "
                       "Relaunch flags are not proof of a later live notice or current buying intent. "
                       "Estimated procedure values are not spend, lost sales or AgentMine demand."}


def run(fetch_page=post_json):
    def all_versions(body):
        return fetch_page({**body, "onlyLatestVersions": False})
    return review(collect(QUERY, fetch_page=all_versions, fields=PROJECTION, max_pages=5, limit=100))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    # One compact line, no raw titles, buyer names, contacts or private data.
    print("AGENTMINE_RESULT_JSON=" + json.dumps(result, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
