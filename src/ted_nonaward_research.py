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
    return value is True or value == "true" or (isinstance(value, list) and len(value) == 1
            and (value[0] is True or value[0] == "true"))


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



def _uniform_status(row):
    lots = _values(row.get("result-lot-identifier"))
    statuses = _values(row.get("winner-selection-status"))
    if (not lots or not all(isinstance(x, str) and re.fullmatch(r"LOT-[0-9]{4}", x) for x in lots)
            or len(set(lots)) != len(lots) or len(statuses) != len(lots)
            or not all(isinstance(x, str) and x in STATUSES for x in statuses)):
        return "unknown"
    return statuses[0] if len(set(statuses)) == 1 else "mixed"


def _uniform_closed_reason(row):
    if _uniform_status(row) != "clos-nw":
        return None
    reasons = _values(row.get("non-award-justification"))
    if (len(reasons) != len(_values(row.get("result-lot-identifier")))
            or not all(isinstance(x, str) and x in REASONS for x in reasons)
            or len(set(reasons)) != 1):
        return "unknown_or_mixed"
    return reasons[0]


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
    primary_ids = {r["publication_number"] for r in primary}
    primary_raw = [r for r in snapshot["notices"] if _id(r["publication-number"]) in primary_ids]
    return {"evidence_type": "official_TED_result_notice_nonaward_research_not_live_Rfq",
            "source_url": ENDPOINT, "observed_at": snapshot["observed_at"], "query": QUERY,
            "only_latest_versions": False, "reported_total_notices": snapshot["reported_total_notices"],
            "pages_fetched": snapshot["pages_fetched"], "complete_for_query": True,
            "projection": PROJECTION, "notice_count": len(rows),
            "main_cpv_scope_counts": dict(Counter(r["main_cpv_scope"] for r in rows)),
            "primary_it_notice_count": len(primary),
            "primary_it_notice_level_status_counts": dict(Counter(_uniform_status(r) for r in primary_raw)),
            "primary_it_uniform_closed_reason_counts": dict(Counter(_uniform_closed_reason(r)
                for r in primary_raw if _uniform_status(r) == "clos-nw")),
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



FOLLOWUP_PAIRS = (("700958-2026", "749334-2026"), ("694643-2026", "778905-2026"))
FOLLOWUP_IDS = sorted({x for pair in FOLLOWUP_PAIRS for x in pair} | {"729884-2026"})
FOLLOWUP_PROJECTION = FIELDS + [
    "procedure-identifier", "notice-version", "form-type", "main-classification-proc",
    "buyer-identifier", "buyer-person", "internal-identifier-proc", "title-proc",
    "identifier-lot", "result-lot-identifier", "winner-selection-status",
    "non-award-justification", "received-submissions-type-code", "received-submissions-type-val",
    "estimated-value-proc", "estimated-value-cur-proc", "result-value-notice", "result-value-cur-notice",
    "deadline-receipt-tender-date-lot", "deadline-receipt-tender-time-lot",
    "deadline-receipt-request-date-lot", "deadline-receipt-request-time-lot",
    "change-notice-version-identifier",
]
FOLLOWUP_PUBLIC = [x for x in FOLLOWUP_PROJECTION if x not in
                   {"buyer-name", "notice-title", "buyer-identifier", "buyer-person", "title-proc"}]


def replay(evidence):
    """Recompute the frozen official projection offline; never refresh its timestamp."""
    if (evidence.get("evidence_type") != "official_TED_result_notice_nonaward_research_not_live_Rfq"
            or evidence.get("only_latest_versions") is not False):
        raise ValueError("unexpected frozen evidence type")
    raw = evidence["public_projection_rows"]
    snapshot = {"source_url": evidence["source_url"], "observed_at": evidence["observed_at"],
                "query": evidence["query"], "scope": "ALL", "pagination_mode": "ITERATION",
                "evidence_type": "public_tender_notices_not_agent_payments",
                "pages_fetched": evidence["pages_fetched"],
                "reported_total_notices": evidence["reported_total_notices"],
                "unique_notices_collected": len(raw), "complete": evidence["complete_for_query"],
                "notices": raw}
    result = review(snapshot)
    for key in ("notice_count", "main_cpv_scope_counts", "primary_it_notice_count",
                "primary_it_classification_counts", "primary_it_closed_reason_counts",
                "primary_it_zero_tender_notice_ids", "rows"):
        if result[key] != evidence[key]:
            raise ValueError("frozen result replay differs: " + key)
    return result


def _equal_present(a, b):
    return a is not None and a != [] and a != "" and a == b


def followup(fetch_page=post_json):
    """Two selected potential re-tenders; exact-ID and procedure-history checks.

    Candidate selection is post-hoc, not a relaunch prevalence estimate. Compare
    public institutional labels/identifiers in memory; do not export them.
    """
    def query(field, values):
        q = f"{field} IN ({' '.join(values)})"
        snapshot = collect(q, fetch_page=lambda body: fetch_page({**body, "onlyLatestVersions": False}),
                           fields=FOLLOWUP_PROJECTION, max_pages=3, limit=100)
        summarize(snapshot)
        if not snapshot["complete"]:
            raise ValueError("incomplete selected follow-up query")
        return snapshot
    first = query("publication-number", FOLLOWUP_IDS)
    by_id = {_id(r["publication-number"]): r for r in first["notices"]}
    if len(by_id) != len(first["notices"]) or set(by_id) != set(FOLLOWUP_IDS):
        raise ValueError("selected publication identity mismatch")
    for old, new in FOLLOWUP_PAIRS:
        if (_single(by_id[old].get("form-type")) != "result"
                or _single(by_id[new].get("form-type")) != "competition"):
            raise ValueError("selected result/competition type mismatch")
    procedures = sorted({_procedure(by_id[new].get("procedure-identifier")) for _, new in FOLLOWUP_PAIRS}
                        - {None})
    if len(procedures) != len(FOLLOWUP_PAIRS):
        raise ValueError("missing or shared candidate procedure identifier")
    history = query("procedure-identifier", procedures)
    history_by_id = {_id(r["publication-number"]): r for r in history["notices"]}
    if (len(history_by_id) != len(history["notices"])
            or any(_procedure(r.get("procedure-identifier")) not in procedures for r in history["notices"])
            or any(history_by_id.get(new) != by_id[new] for _, new in FOLLOWUP_PAIRS)):
        raise ValueError("selected procedure history identity mismatch")
    pairs = []
    for old, new in FOLLOWUP_PAIRS:
        a, b = by_id[old], by_id[new]
        pid = _procedure(b.get("procedure-identifier"))
        related = [r for r in history["notices"] if _procedure(r.get("procedure-identifier")) == pid]
        old_date = date.fromisoformat(_single(a.get("publication-date"))[:10])
        new_date = date.fromisoformat(_single(b.get("publication-date"))[:10])
        if new_date <= old_date:
            raise ValueError("candidate must be published after selected result")
        pairs.append({"prior_result_id": old, "later_competition_id": new,
                      "publication_day_gap": (new_date-old_date).days,
                      "same_buyer_label": _equal_present(a.get("buyer-name"), b.get("buyer-name")),
                      "same_buyer_identifier_projection": _equal_present(a.get("buyer-identifier"), b.get("buyer-identifier")),
                      "same_internal_reference": _equal_present(a.get("internal-identifier-proc"), b.get("internal-identifier-proc")),
                      "same_title_projection": _equal_present(a.get("title-proc"), b.get("title-proc")),
                      "same_estimated_value_and_currency": (
                          _equal_present(a.get("estimated-value-proc"), b.get("estimated-value-proc"))
                          and _equal_present(a.get("estimated-value-cur-proc"), b.get("estimated-value-cur-proc"))),
                      "distinct_procedure_identifiers": _procedure(a.get("procedure-identifier")) != pid,
                      "later_procedure_publication_ids": sorted(_id(r["publication-number"]) for r in related),
                      "later_procedure_result_ids": sorted(_id(r["publication-number"]) for r in related
                          if _single(r.get("form-type")) == "result"),
                      "later_procedure_change_reference_ids": sorted(_id(r["publication-number"]) for r in related
                          if r.get("change-notice-version-identifier")),
                      "legal_relaunch_link_verified": None, "live_portal_cutoff_verified": None})
    return {"evidence_type": "selected_official_TED_result_to_competition_candidates",
            "source_url": ENDPOINT, "observed_at": history["observed_at"], "only_latest_versions": False,
            "queries": [{"query": s["query"], "observed_at": s["observed_at"],
                         "reported_total_notices": s["reported_total_notices"], "complete": s["complete"]}
                        for s in (first, history)],
            "pairs": pairs,
            "public_exact_id_rows": [{k: r[k] for k in FOLLOWUP_PUBLIC if k in r} for r in first["notices"]],
            "public_history_rows": [{k: r[k] for k in FOLLOWUP_PUBLIC if k in r} for r in history["notices"]],
            "verified_live_unmet_needs": None, "verified_agentmine_demand": None,
            "warning": "Selected candidate links, not verified legal re-tenders or current portal status. "
                       "Matching buyer, title, reference or estimate does not establish a causal link. "
                       "No payments, customer interest, supplier eligibility or opportunity value inferred."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--input", type=Path, help="replay frozen official projection offline")
    mode.add_argument("--followup", action="store_true", help="bounded selected exact-ID and procedure queries")
    args = parser.parse_args()
    result = (replay(json.loads(args.input.read_text(encoding="utf-8"))) if args.input else
              followup() if args.followup else run())
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    # One compact line, no raw titles, buyer names, contacts or private data.
    print("AGENTMINE_RESULT_JSON=" + json.dumps(result, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
