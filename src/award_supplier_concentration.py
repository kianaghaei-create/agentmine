"""Offline supplier-award concentration from explicitly selected TED award lots.

Counts observed award lots, NOT the Swedish CPV48 market. No network access.
Inputs must be manually checked against official TED notices. Registry IDs
are jurisdiction-scoped; names are labels, never identity keys.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

_NOTICE = re.compile(r"^[1-9][0-9]{0,7}-20[0-9]{2}$")
_LOT = re.compile(r"^LOT-[0-9]{4,8}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")


def _money(value):
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("award_value_sek must be a decimal string or null")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid award value") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("award value must be finite and nonnegative")
    return amount


def analyze(records, *, min_awarded_lots=5):
    """Calculate descriptive, conditional sample shares with strict suppression.

    One row per notice/lot. Multi-winner lots must remain unknown until
    modeled at contract level; do not duplicate total lot value per winner.
    """
    if not isinstance(records, list) or type(min_awarded_lots) is not int or min_awarded_lots < 2:
        raise ValueError("invalid records or threshold")
    seen = set()
    winners = Counter()
    amounts = defaultdict(Decimal)
    awarded = unknown = non_award = missing_id = missing_amount = 0
    total_bids = 0
    bids_covered = 0
    notices = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("lot must be object")
        number, lot = row.get("notice_number"), row.get("lot_id")
        if not isinstance(number, str) or not _NOTICE.fullmatch(number):
            raise ValueError("invalid TED notice number")
        if not isinstance(lot, str) or not _LOT.fullmatch(lot):
            raise ValueError("invalid lot ID")
        key = (number, lot)
        if key in seen:
            raise ValueError("duplicate notice/lot")
        seen.add(key)
        notices.add(number)
        # TED publishes original notices in several official language routes.
        # Require an exact HTTPS TED PDF path, but do not discard the Swedish
        # original in favor of an English URL that was never retrieved.
        official_urls = {f"https://ted.europa.eu/{language}/notice/{number}/pdf"
                         for language in ("en", "sv")}
        if row.get("source_url") not in official_urls:
            raise ValueError("official TED PDF URL required")
        if row.get("source_kind") != "manual_official_pdf_transcription":
            raise ValueError("explicit manual source provenance required")
        if row.get("cpv_main") != "48000000":
            raise ValueError("only main CPV 48000000 is in scope")
        status = row.get("outcome")
        if status not in {"awarded", "non_award", "unknown"}:
            raise ValueError("invalid outcome")
        bid_count = row.get("tenders_received")
        if bid_count is not None and (type(bid_count) is not int or bid_count < 0):
            raise ValueError("invalid bid count")
        value = _money(row.get("award_value_sek"))
        country, supplier_id = row.get("winner_country"), row.get("winner_registration")
        if status != "awarded":
            if value is not None or country is not None or supplier_id is not None:
                raise ValueError("non-award/unknown cannot carry winning supplier or value")
            if status == "non_award":
                non_award += 1
            else:
                unknown += 1
            continue
        awarded += 1
        if bid_count is not None:
            total_bids += bid_count
            bids_covered += 1
        if value is None:
            missing_amount += 1
        if country is None and supplier_id is None:
            missing_id += 1
            continue
        if (not isinstance(country, str) or not _COUNTRY.fullmatch(country)
                or not isinstance(supplier_id, str) or not supplier_id.strip()
                or len(supplier_id) > 80 or supplier_id != supplier_id.strip()):
            raise ValueError("invalid winner identity")
        identity = f"{country}:{supplier_id}"
        winners[identity] += 1
        if value is not None:
            amounts[identity] += value
    eligible = awarded >= min_awarded_lots and missing_id == 0
    value_eligible = eligible and missing_amount == 0 and sum(amounts.values()) > 0
    shares = [n / awarded for n in winners.values()] if eligible else []
    total_value = sum(amounts.values()) if value_eligible else Decimal(0)
    value_shares = [v / total_value for v in amounts.values()] if value_eligible else []
    return {
        "source_basis": "selected_manual_official_ted_pdf_transcriptions",
        "scope": "selected_award_lots_not_market_census",
        "selected_notice_count": len(notices),
        "selected_lot_count": len(seen),
        "awarded_lots": awarded,
        "non_awarded_lots": non_award,
        "unknown_outcome_lots": unknown,
        "awarded_lots_missing_winner_id": missing_id,
        "awarded_lots_missing_value": missing_amount,
        "awarded_lots_with_bid_count": bids_covered,
        "sum_reported_bids_in_awarded_lots": total_bids,
        "distinct_registered_winner_ids_in_selected_lots": len(winners),
        "award_count_sample_top_supplier_share": round(max(shares), 4) if shares else None,
        "award_count_sample_hhi": round(sum(s*s for s in shares), 4) if shares else None,
        "award_value_sample_top_supplier_share": float(round(max(value_shares), 4)) if value_shares else None,
        "award_value_sample_hhi": float(round(sum(s*s for s in value_shares), 4)) if value_shares else None,
        "supplier_market_hhi": None,
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue_sek": None,
        "suppression_reason": ("too_few_awarded_lots" if awarded < min_awarded_lots else
                               "missing_winner_identity" if missing_id else None),
        "warning": "Only manually transcribed selected official TED lots; not an exhaustive CPV48 census. "
                   "One winner per awarded lot required; do not count multiple winners by duplicating lot value. "
                   "Registered IDs are not independently checked against company registries. "
                   "Tender counts are not distinct bidders or AgentMine demand; awards are not verified payments.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--min-awarded-lots", type=int, default=5)
    args = p.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(analyze(data["records"], min_awarded_lots=args.min_awarded_lots), indent=2))


if __name__ == "__main__":
    main()
