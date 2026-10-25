"""Targeted read-only official TED check of the single unresolved CPV7231 procedure.

A same-procedure notice outside CPV7231 is an identity link, NOT proof that
a competitor failed to find a tender. No raw publication IDs or UUIDs are emitted.
"""
from collections import Counter
from datetime import date
from src.ted_cross_month_procedure import triage_cross_month
from src.ted_notice_evidence import collect, ENDPOINT
from src.ted_procedure_gap_triage import _procedure

START = date(2026, 1, 1)
END = date(2026, 10, 25)


def _query(procedure):
    proc = _procedure(procedure)
    if proc is None:
        raise ValueError("missing procedure identifier")
    return ('procedure-identifier = "' + proc + '" AND '
            'publication-date >= 20260101 AND publication-date <= 20261025')


def _target(september_notices, matched_ids, unmatched_contract_notices, extended_snapshot):
    # Reuse the strict complete-cohort validation, including September membership.
    triage_cross_month(september_notices, matched_ids, unmatched_contract_notices,
                       extended_snapshot)
    extended = extended_snapshot["notices"]
    by_proc = Counter(_procedure(r.get("procedure-identifier")) for r in extended)
    unresolved = [r for r in unmatched_contract_notices
                  if _procedure(r.get("procedure-identifier")) is not None
                  and by_proc[_procedure(r.get("procedure-identifier"))] == 1]
    if len(unresolved) != 1:
        raise ValueError("expected exactly one unresolved procedure in bounded cohort")
    target = unresolved[0]
    return target["publication-number"], _procedure(target["procedure-identifier"])


def _summarize(target_number, procedure, snapshot):
    query = _query(procedure)
    if (not isinstance(snapshot, dict) or snapshot.get("source_url") != ENDPOINT
            or snapshot.get("query") != query or snapshot.get("scope") != "ALL"
            or snapshot.get("complete") is not True
            or not isinstance(snapshot.get("notices"), list)
            or type(snapshot.get("reported_total_notices")) is not int
            or snapshot["reported_total_notices"] != len(snapshot["notices"])
            or snapshot.get("unique_notices_collected") != len(snapshot["notices"])):
        raise ValueError("incomplete or mismatched targeted TED search")
    rows = snapshot["notices"]
    numbers = set()
    months, cpv_categories, types = Counter(), Counter(), Counter()
    target_found = False
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid targeted TED row")
        number = row.get("publication-number")
        if not isinstance(number, str) or not number or number in numbers:
            raise ValueError("duplicate or invalid targeted publication number")
        numbers.add(number)
        if _procedure(row.get("procedure-identifier")) != procedure:
            raise ValueError("targeted search returned different procedure UUID")
        stamp = row.get("publication-date")
        if not isinstance(stamp, str) or len(stamp) < 10:
            raise ValueError("missing targeted publication date")
        try:
            day = date.fromisoformat(stamp[:10])
        except ValueError as exc:
            raise ValueError("invalid targeted publication date") from exc
        if not START <= day <= END:
            raise ValueError("targeted TED date outside bounds")
        if number == target_number:
            target_found = True
            continue
        months[stamp[:7]] += 1
        cpvs = row.get("classification-cpv")
        if cpvs is None or cpvs == []:
            cpv_categories["missing_cpv_unknown"] += 1
        elif not isinstance(cpvs, list) or not all(
                isinstance(c, str) and len(c) == 8 and c.isascii()
                and c.isdecimal() for c in cpvs):
            raise ValueError("invalid targeted CPV projection")
        elif any(c.startswith("7231") for c in cpvs):
            cpv_categories["has_7231_cpv"] += 1
        else:
            cpv_categories["outside_7231_cpv"] += 1
        kind = row.get("notice-type")
        if isinstance(kind, str) and kind.startswith("cn-"):
            types["contract_notice"] += 1
        elif isinstance(kind, str) and kind.startswith("can-"):
            types["award_notice"] += 1
        else:
            types["other_or_unknown"] += 1
    if not target_found:
        raise ValueError("targeted search did not return its target notice")
    return {
        "evidence_type": "official_TED_targeted_procedure_identity_not_competitor_recall",
        "source_url": ENDPOINT,
        "publication_window": "2026-01-01/2026-10-25",
        "complete_for_exact_procedure_query": True,
        "notices_in_procedure": len(rows),
        "peer_notices": len(rows) - 1,
        "peer_publication_months": dict(sorted(months.items())),
        "peer_cpv_categories": dict(sorted(cpv_categories.items())),
        "peer_notice_types": dict(sorted(types.items())),
        "verified_new_distinct_procurement": None,
        "verified_incumbent_search_miss": None,
        "verified_buyer_demand": None,
        "warning": "Only one previously unresolved September contract procedure is queried across all CPVs in a bounded 2026 window. Same UUID indicates a TED procedure link, not another opportunity, active deadline, competitor recall failure, or paying demand. No IDs, titles or UUIDs are emitted."
    }


def probe(september_notices, matched_ids, unmatched_contract_notices,
          extended_snapshot, *, fetch_page=None, fields=None):
    """Fetch a narrowly targeted public TED procedure; return aggregates only.

    Any incomplete or inconsistent source fails closed. Query containing the
    official UUID remains in memory and is never included in the report.
    """
    number, procedure = _target(september_notices, matched_ids,
                                unmatched_contract_notices, extended_snapshot)
    kwargs = {"max_pages": 2, "limit": 100, "fields": fields}
    if fetch_page is not None:
        kwargs["fetch_page"] = fetch_page
    snapshot = collect(_query(procedure), **kwargs)
    return _summarize(number, procedure, snapshot)
