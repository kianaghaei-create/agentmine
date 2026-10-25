"""Read-only TED notice snapshots; public tenders are NOT paid agent demand.
Official API: https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = ["publication-number", "publication-date", "notice-type", "notice-title",
          "buyer-name", "buyer-country", "classification-cpv"]


def request_body(query, limit=50, token=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("invalid TED query")
    if type(limit) is not int or not 1 <= limit <= 250:
        raise ValueError("limit must be integer 1..250")
    if token is not None and (not isinstance(token, str) or not token.strip()):
        raise ValueError("invalid iteration token")
    body = {"query": query, "fields": FIELDS, "limit": limit,
            "scope": "ALL", "paginationMode": "ITERATION", "onlyLatestVersions": True}
    if token is not None:
        body["iterationNextToken"] = token
    return body


def post_json(body):
    payload = json.dumps(body).encode()
    req = Request(ENDPOINT, data=payload, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "AgentMineResearch/0.1 (read-only)"})
    with urlopen(req, timeout=15) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("TED response too large")
    return json.loads(data)


def _notice_id(row):
    if not isinstance(row, dict):
        raise ValueError("notice must be object")
    value = row.get("publication-number")
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise ValueError("invalid publication-number")
    return value


def collect(query, fetch_page=post_json, *, max_pages=2, limit=50, observed_at=None):
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError("invalid max_pages")
    body = request_body(query, limit)
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    try:
        stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid observed_at") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("observed_at must have timezone")
    seen, rows, tokens = {}, [], set()
    total, next_token, complete, pages = None, None, False, 0
    for _ in range(max_pages):
        payload = fetch_page(dict(body))
        if not isinstance(payload, dict) or type(payload.get("timedOut", False)) is not bool:
            raise ValueError("invalid TED response")
        if payload.get("timedOut"):
            raise ValueError("TED search timed out")
        batch, count = payload.get("notices"), payload.get("totalNoticeCount")
        if not isinstance(batch, list) or type(count) is not int or count < 0 or len(batch) > limit:
            raise ValueError("invalid notices/totalNoticeCount")
        if total is not None and total != count:
            raise ValueError("TED totalNoticeCount changed")
        total, pages = count, pages + 1
        for row in batch:
            identifier = _notice_id(row)
            if identifier in seen:
                if seen[identifier] != row:
                    raise ValueError("conflicting duplicate publication-number")
                continue
            seen[identifier] = row
            rows.append(row)
        next_token = payload.get("iterationNextToken")
        if next_token is not None and (not isinstance(next_token, str) or not next_token.strip()):
            raise ValueError("invalid iteration token")
        # TED can return an iteration token even after all reported unique
        # publication numbers have been collected. Do not mark a full page
        # as partial solely because a terminal token is still present.
        if len(rows) > total:
            raise ValueError("TED unique notices exceed reported total")
        if not next_token or len(rows) == total:
            complete = len(rows) == total
            break
        if next_token in tokens:
            raise ValueError("repeated TED iteration token")
        tokens.add(next_token)
        body["iterationNextToken"] = next_token
    return {"source_url": ENDPOINT, "observed_at": observed_at, "query": query,
            "scope": "ALL", "pagination_mode": "ITERATION", "pages_fetched": pages,
            "reported_total_notices": total, "unique_notices_collected": len(rows),
            "complete": complete, "next_iteration_token": None if complete else next_token,
            "notices": rows, "evidence_type": "public_tender_notices_not_agent_payments"}


def _label(value):
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        values = []
        for entry in value.values():
            if isinstance(entry, str):
                values.append(entry)
            elif isinstance(entry, list):
                values.extend(v for v in entry if isinstance(v, str))
        return next((v.strip() for v in values if v.strip()), None)
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0].strip() or None
    return None


def summarize(snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("notices"), list):
        raise ValueError("invalid TED snapshot")
    rows = snapshot["notices"]
    if type(snapshot.get("complete")) is not bool or snapshot.get("unique_notices_collected") != len(rows):
        raise ValueError("invalid snapshot coverage")
    ids = [_notice_id(row) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate notice in snapshot")
    labels = [_label(row.get("buyer-name")) for row in rows]
    counts = Counter(v.casefold() for v in labels if v)
    known, n = sum(counts.values()), len(rows)
    return {"source_url": snapshot.get("source_url"), "observed_at": snapshot.get("observed_at"),
            "query": snapshot.get("query"), "complete_for_query": snapshot["complete"],
            "notice_count": n, "known_buyer_name_notices": known,
            "buyer_name_label_coverage": known / n if n else None,
            "distinct_unverified_buyer_name_labels": len(counts),
            "largest_buyer_name_notice_share_in_known_sample": max(counts.values()) / known if known else None,
            "buyer_name_hhi_in_known_sample": sum((v / known)**2 for v in counts.values()) if known else None,
            "verified_distinct_buyers": None, "verified_supplier_payments": None,
            "agentmine_revenue": None,
            "warning": "Tender notices are not awards, paid agent demand or AgentMine sales. "
                       "Buyer names are unverified labels; sample HHI is not market HHI."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fetch", action="store_true")
    mode.add_argument("--input", type=Path)
    p.add_argument("--query")
    p.add_argument("--max-pages", type=int, default=2)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.fetch:
        if not args.query or not args.output:
            p.error("--fetch requires --query and --output")
        snapshot = collect(args.query, max_pages=args.max_pages, limit=args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(summarize(snapshot), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
