"""Conservative value-basis checks for public procurement award observations.

A notice-level award total, an estimated procedure value, and a winning bid
are distinct fields. A mismatch is not automatically an error or a saving.
Data from mirrors is not independently verified official TED source data.
"""
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
import re

NOTICE = re.compile(r"^[0-9]{1,8}-20[0-9]{2}$")
PROVENANCE = {"official_xml", "official_api", "mirror_transcription"}


def _amount(value, field):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise ValueError(f"invalid {field}")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid {field}") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"invalid {field}")
    return number


def _notice_url(number, url):
    if not isinstance(url, str):
        raise ValueError("missing TED URL")
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "ted.europa.eu"
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in (f"/en/notice/-/detail/{number}",
                                   f"/sv/notice/-/detail/{number}")):
        raise ValueError("invalid official TED URL")


def analyze(records):
    """Summarize a selected, source-linked set without inventing market shares."""
    if not isinstance(records, list):
        raise ValueError("records must be list")
    seen, rows = set(), []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid record")
        number = record.get("publication_number")
        if not isinstance(number, str) or not NOTICE.fullmatch(number):
            raise ValueError("invalid publication number")
        if number in seen:
            raise ValueError("duplicate notice; aggregate at lot level separately")
        seen.add(number)
        _notice_url(number, record.get("ted_url"))
        provenance = record.get("provenance")
        if not isinstance(provenance, str) or provenance not in PROVENANCE:
            raise ValueError("invalid provenance")
        currency = record.get("currency")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("invalid currency")
        estimate = _amount(record.get("procedure_estimate"), "procedure_estimate")
        award = _amount(record.get("procedure_award_total"), "procedure_award_total")
        bid = _amount(record.get("winning_bid_value"), "winning_bid_value")
        count = record.get("tenders_received")
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("invalid tenders_received")
        winner = record.get("winner_name")
        if winner is not None and (not isinstance(winner, str) or not winner.strip()):
            raise ValueError("invalid winner name")
        flags = []
        if provenance == "mirror_transcription":
            flags.append("official_values_not_independently_verified")
        if award is not None and bid is not None and award != bid:
            flags.append("award_total_differs_from_winning_bid_value")
        if estimate is not None and award is not None and estimate != award:
            flags.append("estimate_differs_from_award_total_not_savings")
        if count is None:
            flags.append("tender_count_missing")
        if count == 0 and winner is not None:
            flags.append("winner_with_zero_reported_tenders_review")
        rows.append({
            "publication_number": number, "ted_url": record["ted_url"],
            "provenance": provenance, "currency": currency,
            "procedure_estimate": str(estimate) if estimate is not None else None,
            "procedure_award_total": str(award) if award is not None else None,
            "winning_bid_value": str(bid) if bid is not None else None,
            "tenders_received": count, "winner_name_label": winner,
            "quality_flags": flags,
            "verified_supplier_revenue": None,
        })
    return {
        "selected_notice_count": len(rows),
        "award_bid_value_mismatch_count": sum(
            "award_total_differs_from_winning_bid_value" in r["quality_flags"] for r in rows),
        "records_marked_official_source": sum(
            r["provenance"] in ("official_xml", "official_api") for r in rows),
        "records": rows,
        "independent_source_authentication": None,
        "market_supplier_concentration": None,
        "verified_paying_agentmine_customers": None,
        "warning": "Selected notices are not a market census. Values are separate bases, not interchangeable "
                   "or additive without lot-level checks. Published awards are not verified paid revenue; "
                   "estimated-versus-awarded differences are not realized savings."
    }
