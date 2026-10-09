"""Read-only x402 market evidence snapshot; never equate wallets with customers.

Data attribution: x402stats — State of x402, https://x402stats.io/data (CC BY 4.0).
The publisher's 'organic' filter is a heuristic, not verified customer/revenue evidence.
"""
import argparse
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://x402stats.io/llms-full.txt"
MAX_BYTES = 150_000
PATTERNS = {
    "reported_volume_usd": r"^- Reported volume \(raw, all wallets\): \$([\d,]+(?:\.\d+)?)$",
    "organic_volume_usd": r"^- Organic volume \(wash-filtered\): \$([\d,]+(?:\.\d+)?)",
    "seller_wallets_any_revenue": r"^- Sellers with any revenue: ([\d,]+)$",
    "qualifying_organic_seller_wallets": r"^- Organic sellers \(.*?\): ([\d,]+)$",
    "median_seller_revenue_usd": r"^- Median seller revenue: \$([\d,]+(?:\.\d+)?)$",
    "top_ten_wallet_volume_pct": r"^- Top-10 wallets hold ([\d.]+)% of reported volume$",
}


def parse(text):
    """Parse source claims with explicit provenance and no buyer inference."""
    if not isinstance(text, str):
        raise ValueError("expected text")
    updated = re.search(r"^Updated: (\S+)$", text, re.MULTILINE)
    license_match = re.search(r"^License: (.+)$", text, re.MULTILINE)
    methodology = re.search(r"^Methodology: (\S+)", text, re.MULTILINE)
    if not (updated and license_match and methodology):
        raise ValueError("missing timestamp, license or methodology")
    weekly = re.search(
        r"^## Weekly raw-vs-organic record \(append-only\)\s*\n"
        r"date, reported_volume_usd, organic_volume_usd, organic_sellers\s*\n"
        r"((?:\d{4}-\d{2}-\d{2},[^\n]*\n?)+)", text, re.MULTILINE)
    if not weekly:
        raise ValueError("missing weekly provenance for headline")
    dates = []
    last_weekly = None
    for line in weekly.group(1).splitlines():
        try:
            cells = [cell.strip() for cell in line.split(",")]
            if len(cells) != 4:
                raise ValueError("weekly row must have four fields")
            day = date.fromisoformat(cells[0])
            raw, organic = Decimal(cells[1]), Decimal(cells[2])
            sellers = int(cells[3])
            if (not raw.is_finite() or not organic.is_finite()
                    or raw < 0 or organic < 0 or organic > raw or sellers < 0):
                raise ValueError("invalid weekly snapshot values")
            dates.append(day)
            last_weekly = (raw, organic, sellers)
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("invalid weekly snapshot row") from exc
    if not dates or dates != sorted(set(dates)):
        raise ValueError("weekly snapshot dates must be unique and increasing")
    as_of = dates[-1]
    updated_dt = datetime.fromisoformat(updated.group(1).replace("Z", "+00:00"))
    if updated_dt.tzinfo is None:
        raise ValueError("source timestamp must include timezone")
    lag_days = (updated_dt.date() - as_of).days
    if lag_days < 0:
        raise ValueError("headline snapshot is dated after source update")
    result = {
        "source_url": SOURCE,
        "source_updated_at": updated.group(1),
        "headline_as_of_date": as_of.isoformat(),
        "headline_lag_days_at_source_update": lag_days,
        "headline_is_over_seven_days_old": lag_days > 7,
        "license": license_match.group(1),
        "methodology": methodology.group(1),
    }
    try:
        for key, pattern in PATTERNS.items():
            match = re.search(pattern, text, re.MULTILINE)
            if not match:
                raise ValueError(f"missing metric: {key}")
            result[key] = Decimal(match.group(1).replace(",", ""))
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("invalid numeric metric") from exc
    if any(v < 0 or not v.is_finite() for v in result.values() if isinstance(v, Decimal)):
        raise ValueError("negative or non-finite metric")
    for headline, weekly_value in (
        ("reported_volume_usd", last_weekly[0]),
        ("organic_volume_usd", last_weekly[1]),
        ("qualifying_organic_seller_wallets", Decimal(last_weekly[2])),
    ):
        expected = (weekly_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    if headline != "qualifying_organic_seller_wallets" else weekly_value)
        if result[headline] != expected:
            raise ValueError(f"headline and weekly record disagree: {headline}")
    if (result["organic_volume_usd"] > result["reported_volume_usd"]
            or result["qualifying_organic_seller_wallets"] > result["seller_wallets_any_revenue"]
            or result["top_ten_wallet_volume_pct"] > 100):
        raise ValueError("inconsistent metrics")
    result["organic_share_of_reported_volume"] = (
        result["organic_volume_usd"] / result["reported_volume_usd"]
        if result["reported_volume_usd"] else None)
    result["qualifying_share_of_revenue_wallets"] = (
        result["qualifying_organic_seller_wallets"] / result["seller_wallets_any_revenue"]
        if result["seller_wallets_any_revenue"] else None)
    result["hypothetical_one_percent_of_organic_volume_usd"] = (
        result["organic_volume_usd"] * Decimal("0.01"))
    result["warning"] = (
        "Headline metrics are dated by the latest weekly observation, not the page update. "
        "Wallets are not distinct businesses or paying customers. Organic is a "
        "publisher-defined heuristic. 1% sensitivity assumes capturing all "
        "reported organic flow; it is not a forecast or attainable revenue claim."
    )
    return result


def fetch_text():
    req = Request(SOURCE, headers={
        "User-Agent": "AgentMineResearch/0.1", "Accept": "text/plain"
    })
    with urlopen(req, timeout=12) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("source too large")
    return data.decode("utf-8")


def save(text, directory):
    directory = Path(directory)
    result = parse(text)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    (directory / f"x402stats_{stamp}_source.txt").write_text(text, encoding="utf-8")
    (directory / f"x402stats_{stamp}_summary.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--fetch", action="store_true", help="Explicit read-only fetch")
    source.add_argument("--input", type=Path, help="Previously saved source text")
    p.add_argument("--output-dir", default="data/raw/x402stats")
    args = p.parse_args()
    body = fetch_text() if args.fetch else args.input.read_text(encoding="utf-8")
    print(json.dumps(save(body, args.output_dir), indent=2, default=str))
