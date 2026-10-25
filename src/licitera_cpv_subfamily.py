"""Offline CPV four-digit niche map from Licitera's free previous-month CSV.

A row can appear in multiple subfamilies. Buyer IDs are unverified publisher
labels, not businesses; publisher status is not a live deadline. Only aggregate
statistics are returned. No HTTP, payments, raw rows or customer data.
Source: https://licitera.se/oppen-data (CC BY 4.0, attribution required).
"""
from collections import Counter

from src.licitera_cpv_segment import _cpvs
from src.licitera_monthly_supply import (
    _rows, _id, _MONTH, _CPV, _publication_date, _concentration,
)

_REQUIRED = {"Internt id", "Köpare-id", "Huvud-CPV", "CPV-koder",
             "Publicerad", "Källreferens"}
_SEGMENTS = ("48", "72")
_STATUSES = {"open", "closed", "awarded", "cancelled"}


def analyze(path, *, expected_month, min_group_rows=5):
    """Rank four-digit CPV families by observed notice rows and buyer diversity.

    Each notice contributes at most one count per four-digit family, even if
    multiple detailed CPV codes match. Suppress sparse family-level details.
    """
    if not isinstance(expected_month, str) or not _MONTH.fullmatch(expected_month):
        raise ValueError("expected_month must be YYYY-MM")
    if type(min_group_rows) is not int or min_group_rows < 2:
        raise ValueError("min_group_rows must be an integer >= 2")
    rows = _rows(path, _REQUIRED)
    seen = set()
    groups = {}
    segment_notices = Counter()
    union_notices = 0
    main_scope_union_notices = 0
    multi_family_notices = 0
    for row in rows:
        identifier = _id(row["Internt id"], "procurement ID")
        if identifier in seen:
            raise ValueError("duplicate procurement ID")
        seen.add(identifier)
        _publication_date(row["Publicerad"].strip(), expected_month)
        main = row["Huvud-CPV"].strip()
        if main and not _CPV.fullmatch(main):
            raise ValueError("invalid main CPV")
        codes = _cpvs(row["CPV-koder"])
        if main:
            codes.add(main)
        families = {code[:4] for code in codes if code[:2] in _SEGMENTS}
        if families:
            union_notices += 1
            if main[:2] in _SEGMENTS:
                main_scope_union_notices += 1
            if len(families) > 1:
                multi_family_notices += 1
        for segment in _SEGMENTS:
            if any(family.startswith(segment) for family in families):
                segment_notices[segment] += 1
        buyer = row["Köpare-id"].strip()
        if buyer:
            buyer = _id(buyer, "buyer ID")
        status = row.get("Status", "").strip().lower()
        status = status if status in _STATUSES else "unknown_or_other"
        for family in families:
            group = groups.setdefault(family, {
                "notice_rows": 0, "main_family_rows": 0,
                "secondary_only_rows": 0,
                "secondary_same_segment_main_rows": 0,
                "secondary_other_segment_main_rows": 0,
                "secondary_outside_scope_main_rows": 0,
                "secondary_missing_main_rows": 0,
                "covered_by_main_union_rows": 0,
                "missed_by_main_union_rows": 0,
                "buyer_ids": Counter(),
                "unknown_buyer_rows": 0, "status_rows": Counter(),
            })
            group["notice_rows"] += 1
            if main[:2] in _SEGMENTS:
                group["covered_by_main_union_rows"] += 1
            else:
                group["missed_by_main_union_rows"] += 1
            if main[:4] == family:
                group["main_family_rows"] += 1
            else:
                group["secondary_only_rows"] += 1
                if not main:
                    group["secondary_missing_main_rows"] += 1
                elif main[:2] == family[:2]:
                    group["secondary_same_segment_main_rows"] += 1
                elif main[:2] in _SEGMENTS:
                    group["secondary_other_segment_main_rows"] += 1
                else:
                    group["secondary_outside_scope_main_rows"] += 1
            if buyer:
                group["buyer_ids"][buyer] += 1
            else:
                group["unknown_buyer_rows"] += 1
            group["status_rows"][status] += 1

    retained = []
    suppressed = 0
    suppressed_memberships = 0
    for family, group in groups.items():
        n = group["notice_rows"]
        if n < min_group_rows:
            suppressed += 1
            suppressed_memberships += n
            continue
        known = sum(group["buyer_ids"].values())
        # Sparse buyer cohorts do not support a meaningful concentration label.
        concentration = (_concentration(group["buyer_ids"])
                         if known >= min_group_rows
                         and len(group["buyer_ids"]) >= min_group_rows else None)
        retained.append({
            "cpv_four_digit_prefix": family,
            "segment": family[:2],
            "notice_rows": n,
            "main_family_rows": group["main_family_rows"],
            "secondary_only_rows": group["secondary_only_rows"],
            "secondary_same_segment_main_rows": group["secondary_same_segment_main_rows"],
            "secondary_other_segment_main_rows": group["secondary_other_segment_main_rows"],
            "secondary_outside_scope_main_rows": group["secondary_outside_scope_main_rows"],
            "secondary_missing_main_rows": group["secondary_missing_main_rows"],
            "covered_by_main_segment_only_rows": (group["main_family_rows"] + group["secondary_same_segment_main_rows"]),
            "missed_by_main_segment_only_rows": (group["secondary_other_segment_main_rows"] + group["secondary_outside_scope_main_rows"] + group["secondary_missing_main_rows"]),
            "covered_by_main_union_rows": group["covered_by_main_union_rows"],
            "missed_by_main_union_rows": group["missed_by_main_union_rows"],
            "distinct_unverified_buyer_ids": len(group["buyer_ids"]),
            "unknown_buyer_id_rows": group["unknown_buyer_rows"],
            "publisher_status_rows_not_live": dict(sorted(group["status_rows"].items())),
            "buyer_id_row_concentration": concentration,
            "concentration_suppressed_reason": (
                None if concentration is not None else "insufficient_known_distinct_buyer_ids"
            ),
        })
    retained.sort(key=lambda g: (-g["notice_rows"],
                                  -g["distinct_unverified_buyer_ids"],
                                  g["cpv_four_digit_prefix"]))
    return {
        "evidence_type": "public_monthly_cpv_subfamily_supply_not_verified_demand",
        "publication_month": expected_month,
        "source_page": "https://licitera.se/oppen-data",
        "license": "CC BY 4.0, public previous-month exports",
        "attribution": "Licitera (licitera.se), CC BY 4.0; Uppgifter: Upphandlingsmyndigheten | Bearbetning: Licitera | Analys: AgentMine",
        "procurement_rows": len(rows),
        "union_48_72_notice_rows": union_notices,
        "union_notices_covered_by_main_48_or_72": main_scope_union_notices,
        "union_notices_missed_by_main_48_or_72": union_notices - main_scope_union_notices,
        "segment_any_notice_rows": dict(segment_notices),
        "notices_in_multiple_four_digit_families": multi_family_notices,
        "minimum_group_rows": min_group_rows,
        "published_subfamily_count": len(retained),
        "suppressed_small_subfamily_count": suppressed,
        "suppressed_small_subfamily_memberships": suppressed_memberships,
        "subfamilies": retained,
        "verified_paying_customers": None,
        "verified_agentmine_revenue": None,
        "warning": "Four-digit CPV labels describe publisher notice supply, not buyer requests or payments. A notice can occur in several families, so family counts cannot be summed into unique notices. Secondary-only at four digits, or missed by the family\'s main segment, does not imply a broad main-CPV 48/72 search misses the notice. Buyer IDs are unverified labels; row HHI is not market share. Publisher 'open' status is not a verified current deadline or actionable opportunity. No customer willingness to pay or time savings measured.",
    }
