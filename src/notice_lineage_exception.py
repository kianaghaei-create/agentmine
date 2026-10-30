"""Offline audit of two public directory listings with reported notice lineage.

A cross-publisher correction claim is NOT independent official TED verification.
No legal deadline, current value, market prevalence, supplier benefit or sale
can be inferred from this diagnostic. No HTTP, payments or personal data.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

_ID = ("725675-2026", "729380-2026")
_LINEAGE = {
    "Tenderiva": "correction_notice_of_725675-2026",
    "Licitera": "same_procurement_both_notice_ids",
}
_HOST = {"Tenderiva": "tenderiva.com", "Licitera": "licitera.se"}


def _money(value):
    if not isinstance(value, str) or not value.isdecimal():
        raise ValueError("amount must be nonnegative integer SEK text")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid SEK amount") from exc


def analyze(evidence):
    if not isinstance(evidence, dict) or evidence.get("evidence_type") != "public_competitor_notice_lineage_exception_not_primary_verified":
        raise ValueError("wrong evidence type")
    if evidence.get("official_primary_verified") is not False:
        raise ValueError("official original and amendment lineage not verified")
    if evidence.get("verified_agentmine_revenue_sek") is not None or evidence.get("verified_supplier_savings") is not None:
        raise ValueError("commercial claims not supported")
    try:
        date.fromisoformat(evidence["observed_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid observation date") from exc
    rows = evidence.get("directory_notice_pages")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("exactly two directory notices required")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid directory row")
        number = row.get("notice_id")
        if number not in _ID or number in by_id:
            raise ValueError("unknown or duplicate notice")
        if row.get("url") != f"https://upphandla.app/en/tender/{number}":
            raise ValueError("directory source not bound to notice")
        if row.get("buyer") != "Kriminalvården" or row.get("title") != "Händelserapporteringssystem":
            raise ValueError("different procurement labels")
        if row.get("deadline") != "2026-11-25" or row.get("cpv") != ["72000000", "48517000", "48614000", "72263000", "72268000"]:
            raise ValueError("different deadline or CPV scope")
        try:
            published = date.fromisoformat(row["published"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid publication date") from exc
        by_id[number] = (published, _money(row.get("value_sek")))
    if not by_id[_ID[0]][0] < by_id[_ID[1]][0]:
        raise ValueError("publication chronology inconsistent")
    claims = evidence.get("lineage_claim_sources")
    if not isinstance(claims, list) or len(claims) != 2:
        raise ValueError("two independent publisher claims required")
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("invalid lineage claim")
        publisher = claim.get("provider")
        if publisher not in _LINEAGE or publisher in seen or claim.get("assertion") != _LINEAGE[publisher]:
            raise ValueError("unsupported or duplicate lineage claim")
        url = claim.get("url")
        if not isinstance(url, str):
            raise ValueError("invalid lineage URL")
        try:
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname != _HOST[publisher] or
                    parsed.username or parsed.password or parsed.port is not None or
                    parsed.query or parsed.fragment or not parsed.path.startswith("/")):
                raise ValueError("invalid lineage URL")
        except ValueError as exc:
            raise ValueError("invalid lineage URL") from exc
        if publisher == "Tenderiva" and "729380-2026" not in parsed.path:
            raise ValueError("Tenderiva notice mismatch")
        if publisher == "Licitera" and parsed.path != "/upphandling/handelserapporteringssystem-7d02885ae3":
            raise ValueError("Licitera procurement mismatch")
        seen.add(publisher)
    old, latest = (by_id[n][1] for n in _ID)
    if latest <= 0:
        raise ValueError("newer displayed amount must be positive")
    return {
        "observation_date": evidence["observed_date"],
        "directory_listings": 2,
        "independent_third_party_lineage_claim_sources": len(seen),
        "older_directory_amount_sek": str(old),
        "newer_directory_amount_sek": str(latest),
        "older_to_newer_display_ratio": str(old / latest),
        "naively_summed_directory_amount_sek": str(old + latest),
        "naive_sum_to_newer_display_ratio": str((old + latest) / latest),
        "verified_current_legal_contract_value_sek": None,
        "verified_operative_deadline": None,
        "verified_supplier_savings": None,
        "verified_paying_customers": None,
        "verified_agentmine_revenue_sek": None,
        "population_prevalence": None,
        "lineage_status": "correction_reported_by_two_third_parties_not_officially_verified",
        "warning": "Two third-party sources group the notices; Tenderiva labels the newer one a correction. The official TED originals and amendments were inaccessible. The newer directory amount is NOT independently verified as legally operative. One case does not establish error prevalence, buyer demand or savings.",
    }
