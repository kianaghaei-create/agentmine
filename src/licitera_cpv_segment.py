"""Offline CPV48/72 segment scope and buyer-label concentration from public Licitera monthly CSV.

Input: explicitly public previous-month CC BY 4.0 procurement export only.
No network requests, personal data, raw record output, payment or inferred buyers.
Main CPV and any-listed CPV are different denominators; a notice may be in both
segments when considering all CPV codes. See https://licitera.se/oppen-data.
"""
import argparse
from collections import Counter
from datetime import date
import json
import re
from pathlib import Path

from src.licitera_monthly_supply import _rows, _concentration, _MONTH, _CPV

_REQUIRED = {"Internt id", "Köpare-id", "Huvud-CPV", "CPV-koder", "Publicerad", "Källreferens", "Källa"}
_SEGMENTS = ("48", "72")


def _cpvs(value):
    if not isinstance(value, str):
        raise ValueError("invalid CPV list")
    values = value.split()
    if len(values) > 100 or any(not _CPV.fullmatch(v) for v in values):
        raise ValueError("invalid CPV list")
    return set(values)


def analyze(path, *, expected_month):
    if not isinstance(expected_month, str) or not _MONTH.fullmatch(expected_month):
        raise ValueError("expected_month must be YYYY-MM")
    rows = _rows(path, _REQUIRED)
    seen_ids = set()
    seen_refs = set()
    collisions = 0
    missing_ref = 0
    missing_main = 0
    main_not_in_list = 0
    unknown_buyer = 0
    counters = {s: {"main": 0, "any": 0, "any_only": 0, "known_buyer": Counter(),
                    "unknown_buyer": 0} for s in _SEGMENTS}
    both_any = 0
    for row in rows:
        ident = row["Internt id"].strip()
        if not ident or len(ident) > 160 or ident in seen_ids:
            raise ValueError("missing or duplicate procurement ID")
        seen_ids.add(ident)
        published_text = row["Publicerad"].strip()
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", published_text):
            raise ValueError("invalid publication date")
        try:
            published = date.fromisoformat(published_text)
        except ValueError as exc:
            raise ValueError("invalid publication date") from exc
        if published.strftime("%Y-%m") != expected_month:
            raise ValueError("procurement outside expected publication month")
        main = row["Huvud-CPV"].strip()
        if main and not _CPV.fullmatch(main):
            raise ValueError("invalid main CPV")
        if not main:
            missing_main += 1
        all_cpvs = _cpvs(row["CPV-koder"])
        if main and all_cpvs and main not in all_cpvs:
            main_not_in_list += 1
        buyer = row["Köpare-id"].strip()
        if len(buyer) > 160:
            raise ValueError("invalid buyer ID")
        if not buyer:
            unknown_buyer += 1
        source = row["Källa"].strip().lower()
        ref = row["Källreferens"].strip()
        if ref:
            if len(ref) > 200 or len(source) > 80:
                raise ValueError("invalid source reference")
            key = (source, ref)
            if key in seen_refs:
                collisions += 1
            seen_refs.add(key)
        else:
            missing_ref += 1
        any_segments = {cpv[:2] for cpv in all_cpvs if cpv[:2] in _SEGMENTS}
        if main and main[:2] in _SEGMENTS:
            any_segments.add(main[:2])  # Preserve main category when list is missing/inconsistent.
        if len(any_segments) == 2:
            both_any += 1
        for segment in _SEGMENTS:
            main_hit = bool(main) and main.startswith(segment)
            any_hit = segment in any_segments
            if main_hit:
                counters[segment]["main"] += 1
            if any_hit:
                c = counters[segment]
                c["any"] += 1
                c["any_only"] += int(not main_hit)
                if buyer:
                    c["known_buyer"][buyer] += 1
                else:
                    c["unknown_buyer"] += 1
    return {
        "evidence_type": "public_monthly_procurement_supply_not_demand",
        "source_url": "https://licitera.se/oppen-data",
        "license": "CC BY 4.0 monthly exports; attribution required",
        "attribution": "Licitera (licitera.se), CC BY 4.0; Uppgifter: Upphandlingsmyndigheten | Bearbetning: Licitera | Analys: AgentMine",
        "publication_month": expected_month,
        "rows": len(rows),
        "missing_main_cpv_rows": missing_main,
        "main_cpv_absent_from_nonempty_all_cpv_list_rows": main_not_in_list,
        "missing_source_reference_rows": missing_ref,
        "duplicate_source_reference_rows": collisions,
        "unique_source_reference_labels": len(seen_refs),
        "unknown_buyer_id_rows": unknown_buyer,
        "rows_with_both_48_and_72_any_cpv": both_any,
        "segments": {
            s: {
                "main_cpv_rows": c["main"],
                "any_cpv_rows": c["any"],
                "secondary_cpv_only_rows": c["any_only"],
                "any_cpv_unknown_buyer_id_rows": c["unknown_buyer"],
                "any_cpv_buyer_id_concentration": _concentration(c["known_buyer"]),
            } for s, c in counters.items()
        },
        "verified_paying_customers": None,
        "verified_supplier_businesses": None,
        "agentmine_revenue_sek": None,
        "warning": "Monthly publisher subset, not national market or agent demand. Any-CPV segments overlap; "
                   "source reference collisions are flags, not proven duplicates. Buyer IDs are unverified labels; "
                   "HHI is a row-frequency concentration in this file, not market share. "
                   "Missing CPV list may understate any-CPV coverage; no bid counts or paid conversions.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procurements", type=Path, required=True)
    parser.add_argument("--month", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.procurements, expected_month=args.month), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
