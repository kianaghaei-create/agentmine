"""Read-only x402 discovery collector. Standard library only."""
import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_URL = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources"
FIELDS = ["resource", "service_name", "description", "tags", "type", "network",
          "asset", "amount_atomic", "pay_to", "calls_30d", "payers_30d",
          "last_called_at", "last_updated", "collected_at", "source"]


def normalize(item, collected_at, source):
    accepts = item.get("accepts") or []
    payment = accepts[0] if accepts and isinstance(accepts[0], dict) else {}
    quality = item.get("quality") or {}
    info = item.get("resource")
    resource = info.get("url", "") if isinstance(info, dict) else info or ""
    return {
        "resource": resource, "service_name": item.get("serviceName") or "",
        "description": item.get("description") or "",
        "tags": "|".join(item.get("tags") or []),
        "type": item.get("type") or "",
        "network": payment.get("network") or "",
        "asset": payment.get("asset") or "",
        "amount_atomic": payment.get("amount", payment.get("maxAmountRequired", "")),
        "pay_to": payment.get("payTo") or "",
        "calls_30d": quality.get("l30DaysTotalCalls"),
        "payers_30d": quality.get("l30DaysUniquePayers"),
        "last_called_at": quality.get("lastCalledAt"),
        "last_updated": item.get("lastUpdated"),
        "collected_at": collected_at, "source": source,
    }


def request_page(url, token, offset, limit, retries=3):
    query = urllib.parse.urlencode({"limit": limit, "offset": offset})
    target = url + ("&" if "?" in url else "?") + query
    headers = {"Accept": "application/json", "User-Agent": "AgentMineResearch/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(target, headers=headers), timeout=25
            ) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError("Authentication denied. Set CDP_BEARER_TOKEN or use an authorized source.") from exc
            if exc.code not in (429, 500, 502, 503) or attempt == retries - 1:
                raise
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError("Retries exhausted")


def collect(url, token, max_items=100, page_size=100, delay=0.3):
    timestamp = datetime.now(timezone.utc).isoformat()
    raw_pages, rows, seen = [], [], set()
    offset = 0
    while len(rows) < max_items:
        page = request_page(url, token, offset, min(page_size, max_items - len(rows)))
        raw_pages.append(page)
        items = page.get("items", page.get("resources", []))
        if not isinstance(items, list):
            raise ValueError("Unexpected discovery response: missing items list")
        for item in items:
            if not isinstance(item, dict):
                continue
            row = normalize(item, timestamp, url)
            identity = (row["resource"], row["type"])
            if not row["resource"] or identity in seen:
                continue
            seen.add(identity)
            rows.append(row)
            if len(rows) >= max_items:
                break
        offset += len(items)
        total = (page.get("pagination") or {}).get("total")
        if not items or (total is not None and offset >= total) or len(items) < min(page_size, max_items - (offset - len(items))):
            break
        time.sleep(delay)
    return raw_pages, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--out", default="data/output")
    args = parser.parse_args()
    if args.max_items < 1 or args.max_items > 10000:
        parser.error("--max-items must be 1..10000")
    token = os.environ.get("CDP_BEARER_TOKEN")
    try:
        pages, rows = collect(args.url, token, args.max_items)
    except (RuntimeError, urllib.error.URLError, ValueError) as exc:
        parser.exit(1, f"Collection failed: {exc}\n")
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (directory / f"raw_{stamp}.json").write_text(json.dumps(pages, indent=2), encoding="utf-8")
    with (directory / f"resources_{stamp}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Collected {len(rows)} unique resources; outputs in {directory}")


if __name__ == "__main__":
    main()
