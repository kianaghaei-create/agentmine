"""Bounded, aggregate-only cross-month TED procedure-identity check.

This is a public-notice identity diagnostic, not evidence of live deadlines,
incumbent product misses, buyer demand or paid customers. Raw notices stay in
memory and only count summaries are returned.
"""
from collections import Counter
from datetime import date
from src.ted_procedure_gap_triage import _procedure

SOURCE = "https://api.ted.europa.eu/v3/notices/search"
CROSS_MONTH_QUERY = (
    "publication-date >= 20260801 AND publication-date <= 20261025 "
    "AND buyer-country = SWE AND classification-cpv = 7231*"
)
START = date(2026, 8, 1)
END = date(2026, 10, 25)


def _checked(snapshot, query):
    if not isinstance(snapshot, dict) or snapshot.get("source_url") != SOURCE:
        raise ValueError("invalid TED source")
    if snapshot.get("query") != query or snapshot.get("scope") != "ALL":
        raise ValueError("unexpected TED query/scope")
    notices = snapshot.get("notices")
    if (snapshot.get("complete") is not True or not isinstance(notices, list)
            or type(snapshot.get("reported_total_notices")) is not int
            or snapshot["reported_total_notices"] != len(notices)
            or snapshot.get("unique_notices_collected") != len(notices)):
        raise ValueError("incomplete or invalid TED cross-month cohort")
    seen = set()
    for row in notices:
        if not isinstance(row, dict):
            raise ValueError("invalid TED notice")
        number = row.get("publication-number")
        if not isinstance(number, str) or number in seen or not number:
            raise ValueError("duplicate/missing TED publication number")
        seen.add(number)
        stamp = row.get("publication-date")
        if not isinstance(stamp, str):
            raise ValueError("missing TED publication date")
        try:
            day = date.fromisoformat(stamp)
        except ValueError as exc:
            raise ValueError("invalid TED publication date") from exc
        if not START <= day <= END:
            raise ValueError("TED notice outside cross-month bounds")
        country = row.get("buyer-country")
        if country != "SWE" and not (
                isinstance(country, list) and "SWE" in country):
            raise ValueError("TED buyer country mismatch")
        cpvs = row.get("classification-cpv")
        if (not isinstance(cpvs, list) or not cpvs
                or not all(isinstance(c, str) and len(c) == 8 and c.isascii()
                           and c.isdecimal() for c in cpvs)
                or not any(c.startswith("7231") for c in cpvs)):
            raise ValueError("TED CPV projection mismatch")
    return notices


def triage_cross_month(september_notices, matched_ids, unmatched_contract_notices,
                       extended_snapshot, september_query):
    """Compare unmatched September contract UUIDs with other TED 7231 notices.

    No match in this bounded CPV/country/time cohort does NOT establish a new
    procurement procedure or absence from a competitor's search product.
    """
    if not isinstance(september_notices, list) or not isinstance(matched_ids, set):
        raise ValueError("invalid September cohort")
    if not isinstance(unmatched_contract_notices, list):
        raise ValueError("invalid unmatched cohort")
    # Check the full extended source, not a user-provided subset.
    extended = _checked(extended_snapshot, CROSS_MONTH_QUERY)
    sept = {r["publication-number"]: r for r in september_notices}
    if len(sept) != len(september_notices) or not matched_ids <= sept.keys():
        raise ValueError("invalid September notice identities")
    ext = {r["publication-number"]: r for r in extended}
    if not sept.keys() <= ext.keys():
        raise ValueError("cross-month cohort missing September notices")
    if any(ext[n].get("publication-date") != r.get("publication-date")
           for n, r in sept.items()):
        raise ValueError("cross-month publication dates disagree")
    if any(not isinstance(r, dict) or r.get("publication-number") not in sept
           or r.get("publication-number") in matched_ids
           for r in unmatched_contract_notices):
        raise ValueError("invalid unmatched contract membership")
    if len({r["publication-number"] for r in unmatched_contract_notices}) != len(unmatched_contract_notices):
        raise ValueError("duplicate unmatched contract")
    proc_by_id = {n: _procedure(r.get("procedure-identifier")) for n, r in ext.items()}
    counts = Counter()
    month_counts = Counter(r["publication-date"][:7] for r in extended)
    for row in unmatched_contract_notices:
        n = row["publication-number"]
        proc = proc_by_id[n]
        if proc is None:
            counts["missing_procedure_identifier"] += 1
            continue
        peers = [ext[m] for m, p in proc_by_id.items() if m != n and p == proc]
        if any(p["publication-number"] in matched_ids for p in peers):
            counts["linked_to_matched_september_notice"] += 1
        elif any(p["publication-date"][:7] == "2026-09" for p in peers):
            counts["linked_to_other_september_notice"] += 1
        elif peers:
            counts["linked_to_august_or_october_notice"] += 1
        else:
            counts["no_link_in_bounded_7231_cohort_not_proof_of_distinct_opportunity"] += 1
    if sum(counts.values()) != len(unmatched_contract_notices):
        raise ValueError("cross-month triage count mismatch")
    return {
        "evidence_type": "official_TED_bounded_procedure_identity_not_competitor_recall",
        "cross_month_query": CROSS_MONTH_QUERY,
        "source_url": SOURCE,
        "extended_complete": True,
        "extended_publication_numbers": len(extended),
        "publication_month_counts": dict(sorted(month_counts.items())),
        "september_notice_numbers_present": len(sept),
        "unmatched_contract_notices": len(unmatched_contract_notices),
        "procedure_link_categories": dict(sorted(counts.items())),
        "verified_new_distinct_procurements": None,
        "verified_incumbent_search_misses": None,
        "verified_supplier_demand": None,
        "warning": "Procedure UUID links are official TED identity evidence only. The August–October CPV7231/SWE cohort is bounded; absence of a link does not prove uniqueness or competitor omission. No notice identifiers, buyer names or procedure UUIDs are emitted."
    }
