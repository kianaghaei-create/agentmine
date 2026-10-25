"""Same-month award-to-notice CPV joins from Licitera's free CC BY 4.0 exports.

Descriptive *award-row* evidence only: the two monthly exports are different
cohorts. Joins are not bid conversion, contract value, market share or customers.
No names, identities, values, or raw tender rows are returned or persisted.
Source: https://licitera.se/oppen-data (attribution required).
"""
from collections import Counter

from src.licitera_monthly_supply import (
    _rows, _id, _MONTH, _CPV, _publication_date, _concentration,
    _REQUIRED_PROC, _REQUIRED_AWARD,
)
from src.licitera_cpv_segment import _cpvs

_SEGMENTS = ("48", "72", "48_or_72")


def analyze(procurement_csv, award_csv, *, expected_month, min_award_rows=5):
    """Count only same-month joins; suppress sparse or incomplete supplier HHI."""
    if not isinstance(expected_month, str) or not _MONTH.fullmatch(expected_month):
        raise ValueError("expected_month must be YYYY-MM")
    if type(min_award_rows) is not int or min_award_rows < 2:
        raise ValueError("min_award_rows must be an integer >= 2")
    procurements = _rows(procurement_csv, _REQUIRED_PROC | {"CPV-koder"})
    by_id = {}
    for row in procurements:
        pid = _id(row["Internt id"], "procurement ID")
        if pid in by_id:
            raise ValueError("duplicate procurement ID")
        _publication_date(row["Publicerad"].strip(), expected_month)
        main = row["Huvud-CPV"].strip()
        if main and not _CPV.fullmatch(main):
            raise ValueError("invalid main CPV")
        listed = _cpvs(row["CPV-koder"])
        codes = {v[:2] for v in listed}
        if main:
            codes.add(main[:2])
        by_id[pid] = (codes, main[:2] if main else None)

    awards = _rows(award_csv, _REQUIRED_AWARD)
    seen_awards = set()
    groups = {key: {"award_rows": 0, "unknown_supplier_rows": 0,
                    "supplier_counts": Counter(), "tender_ids": set(),
                    "main_cpv_award_rows": 0, "secondary_only_award_rows": 0}
              for key in _SEGMENTS}
    matched = unmatched = 0
    for row in awards:
        aid = _id(row["Internt id"], "award ID")
        if aid in seen_awards:
            raise ValueError("duplicate award ID")
        seen_awards.add(aid)
        pid = _id(row["Upphandling-id"], "award procurement ID")
        supplier = row["Leverantör-id"].strip()
        if supplier:
            supplier = _id(supplier, "supplier ID")
        if pid not in by_id:
            unmatched += 1
            continue
        matched += 1
        codes, main = by_id[pid]
        for segment in _SEGMENTS:
            selected = (bool({"48", "72"} & codes) if segment == "48_or_72"
                        else segment in codes)
            if not selected:
                continue
            group = groups[segment]
            group["award_rows"] += 1
            group["tender_ids"].add(pid)
            main_hit = main in ("48", "72") if segment == "48_or_72" else main == segment
            group["main_cpv_award_rows" if main_hit else "secondary_only_award_rows"] += 1
            if supplier:
                group["supplier_counts"][supplier] += 1
            else:
                group["unknown_supplier_rows"] += 1
    result = {}
    for segment, group in groups.items():
        n = group["award_rows"]
        eligible = n >= min_award_rows and group["unknown_supplier_rows"] == 0
        concentration = _concentration(group["supplier_counts"]) if eligible else None
        result[segment] = {
            "matched_award_rows": n,
            "distinct_matched_tender_ids": len(group["tender_ids"]),
            "main_cpv_award_rows": group["main_cpv_award_rows"],
            "secondary_only_award_rows": group["secondary_only_award_rows"],
            "unknown_supplier_id_award_rows": group["unknown_supplier_rows"],
            "distinct_unverified_supplier_ids": len(group["supplier_counts"]),
            "supplier_id_concentration": concentration,
            "concentration_suppressed_reason": (
                "too_few_matched_award_rows" if n < min_award_rows else
                "unknown_supplier_id_rows" if group["unknown_supplier_rows"] else None
            ),
        }
    return {
        "evidence_type": "public_monthly_same_cohort_award_joins_not_buyer_demand",
        "publication_month": expected_month,
        "source_page": "https://licitera.se/oppen-data",
        "license": "CC BY 4.0, previous-month public exports",
        "attribution": "Licitera (licitera.se), CC BY 4.0; Uppgifter: Upphandlingsmyndigheten | Bearbetning: Licitera | Analys: AgentMine",
        "procurement_rows": len(procurements),
        "award_file_rows": len(awards),
        "award_rows_joined_to_same_month_procurements": matched,
        "award_rows_not_joined_to_same_month_procurements": unmatched,
        "segments": result,
        "verified_paying_customers": None,
        "verified_agentmine_revenue": None,
        "supplier_market_share": None,
        "warning": "Award rows and published tenders have different monthly cohorts. Matched award rows are not bids, wins, conversion rates or buyer demand. Supplier IDs are unverified publisher labels. Overlapping CPV groups cannot be summed; any HHI describes only matched award-row frequencies, not market share.",
    }
