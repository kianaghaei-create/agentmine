"""Offline audit of two public directory listings with reported notice lineage.

A cross-publisher correction claim is NOT independent official TED verification.
No legal deadline, current value, market prevalence, supplier benefit or sale
can be inferred from this diagnostic. No HTTP, payments or personal data.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import re

_NOTICE = re.compile(r"^[1-9][0-9]{0,7}-20[0-9]{2}$")
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
        observed_raw = evidence["observed_date"]
        if not isinstance(observed_raw, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", observed_raw):
            raise ValueError("invalid observation date format")
        observed = date.fromisoformat(observed_raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid observation date") from exc
    if observed > datetime.now(timezone.utc).date():
        raise ValueError("observation date cannot be in the future")
    rows = evidence.get("directory_notice_pages")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("exactly two directory notices required")
    by_id = {}
    common = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid directory row")
        number = row.get("notice_id")
        if not isinstance(number, str) or not _NOTICE.fullmatch(number) or number in by_id:
            raise ValueError("invalid or duplicate notice")
        if row.get("url") != f"https://upphandla.app/en/tender/{number}":
            raise ValueError("directory source not bound to notice")
        shared = (row.get("buyer"), row.get("title"), row.get("deadline"), row.get("cpv"))
        buyer, title, deadline, cpv = shared
        if (not isinstance(buyer, str) or not buyer.strip() or
                not isinstance(title, str) or not title.strip() or
                not isinstance(deadline, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", deadline) or
                not isinstance(cpv, list) or not cpv or
                any(not isinstance(c, str) or not re.fullmatch(r"[0-9]{8}", c) for c in cpv)):
            raise ValueError("missing or invalid common procurement fields")
        try:
            date.fromisoformat(deadline)
        except ValueError as exc:
            raise ValueError("invalid calendar deadline") from exc
        if common is not None and shared != common:
            raise ValueError("different procurement labels, deadline or CPV scope")
        common = shared
        try:
            published_raw = row["published"]
            if not isinstance(published_raw, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", published_raw):
                raise ValueError("invalid publication date format")
            published = date.fromisoformat(published_raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid publication date") from exc
        if published > observed:
            raise ValueError("directory publication postdates evidence observation")
        by_id[number] = (published, _money(row.get("value_sek")))
    ordered = sorted(by_id, key=lambda n: by_id[n][0])
    old_id, new_id = ordered
    if by_id[old_id][0] == by_id[new_id][0]:
        raise ValueError("publication chronology inconsistent")
    claims = evidence.get("lineage_claim_sources")
    if not isinstance(claims, list) or len(claims) != 2:
        raise ValueError("two independent publisher claims required")
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("invalid lineage claim")
        publisher = claim.get("provider")
        expected = {"Tenderiva": f"correction_notice_of_{old_id}",
                    "Licitera": "same_procurement_both_notice_ids"}
        if publisher not in expected or publisher in seen or claim.get("assertion") != expected[publisher]:
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
        if publisher == "Tenderiva" and not parsed.path.startswith(f"/sv/tender/{new_id}-"):
            raise ValueError("Tenderiva notice mismatch")
        if publisher == "Licitera" and not re.fullmatch(r"/upphandling/[a-z0-9-]+", parsed.path):
            raise ValueError("Licitera procurement mismatch")
        seen.add(publisher)
    old, latest = by_id[old_id][1], by_id[new_id][1]
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
