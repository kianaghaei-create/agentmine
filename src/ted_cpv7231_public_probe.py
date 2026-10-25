"""Aggregate-only independent TED CPV7231 cohort probe (no raw notice persistence).
Official public search API: https://docs.ted.europa.eu/api/latest/search.html
Not a competitor-recall test, live deadline check, or evidence of paying demand.
"""
import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path

SOURCE = "https://api.ted.europa.eu/v3/notices/search"
QUERY = ("publication-date >= 20260901 AND publication-date <= 20260930 "
         "AND buyer-country = SWE AND classification-cpv = 7231*")
EXPECTED_MONTH = "2026-09"


def summarize(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("source_url") != SOURCE:
        raise ValueError("unexpected TED source")
    if snapshot.get("query") != QUERY or snapshot.get("scope") != "ALL":
        raise ValueError("unexpected TED query or scope")
    if type(snapshot.get("complete")) is not bool:
        raise ValueError("missing completeness status")
    rows = snapshot.get("notices")
    if (not isinstance(rows, list) or type(snapshot.get("unique_notices_collected")) is not int
            or snapshot["unique_notices_collected"] != len(rows)):
        raise ValueError("invalid TED notice count")
    total = snapshot.get("reported_total_notices")
    if type(total) is not int or total < len(rows):
        raise ValueError("invalid TED reported total")
    if snapshot["complete"] and len(rows) != total:
        raise ValueError("complete TED snapshot does not match total")
    stamp = snapshot.get("observed_at")
    if not isinstance(stamp, str):
        raise ValueError("missing observation time")
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observation time") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("observation time must be offset-aware")
    kinds, ids = Counter(), set()
    missing_country = missing_cpv = outside_cpv = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid TED notice")
        ident = row.get("publication-number")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("missing or duplicate publication number")
        ids.add(ident)
        published = row.get("publication-date")
        if not isinstance(published, str) or len(published) < 10:
            raise ValueError("missing TED publication date")
        try:
            published_day = date.fromisoformat(published[:10])
        except ValueError as exc:
            raise ValueError("invalid TED publication date") from exc
        if published_day.strftime("%Y-%m") != EXPECTED_MONTH:
            raise ValueError("TED query returned notice outside publication month")
        country = row.get("buyer-country")
        if country is None:
            missing_country += 1
        elif country != "SWE":
            raise ValueError("TED query returned notice outside Swedish buyers")
        codes = row.get("classification-cpv", [])
        if not isinstance(codes, list) or not all(isinstance(x, str) for x in codes):
            raise ValueError("TED classification-cpv must be a list of strings")
        normalized = {code.strip() for code in codes}
        if any(len(code) != 8 or not code.isascii() or not code.isdecimal() for code in normalized):
            raise ValueError("invalid TED CPV code")
        if not normalized:
            missing_cpv += 1
        elif not any(code.startswith("7231") for code in normalized):
            outside_cpv += 1
        kind = row.get("notice-type")
        if kind is None:
            kind = "unknown"
        elif not isinstance(kind, str):
            raise ValueError("invalid TED notice type")
        elif kind.startswith("cn-"):
            kind = "contract_notice"
        elif kind.startswith("can-"):
            kind = "contract_award_notice"
        else:
            kind = "other"
        kinds[kind] += 1
    return {
        "evidence_type": "independent_ted_cpv7231_public_notice_sample_not_customer_demand",
        "source_url": SOURCE, "query": QUERY, "observed_at": stamp,
        "publication_month": EXPECTED_MONTH, "buyer_country_filter": "SWE",
        "cpv_prefix_filter": "7231", "complete_for_query": snapshot["complete"],
        "reported_total_notices": total,
        "observed_unique_publication_numbers": len(rows),
        "notice_type_counts_in_sample": dict(sorted(kinds.items())),
        "missing_buyer_country_rows": missing_country,
        "missing_classification_cpv_rows": missing_cpv,
        "no_7231_cpv_in_returned_fields_rows": outside_cpv,
        "verified_current_open_deadlines": None,
        "verified_incumbent_search_misses": None,
        "verified_supplier_time_savings": None,
        "verified_paying_agentmine_customers": None,
        "agentmine_revenue": None,
        "interpretation": "TED publication-number cohort, not matched to Licitera procurement IDs. Truncated crawl is a sample only. Search filters do not verify deadlines, competitor recall or paying demand.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from src.ted_notice_evidence import collect
    snapshot = collect(QUERY, max_pages=2, limit=100)
    result = summarize(snapshot)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
