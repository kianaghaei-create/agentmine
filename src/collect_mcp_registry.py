"""Read-only MCP registry collector with preserved raw-page provenance."""
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://registry.modelcontextprotocol.io/v0.1/servers"
MAX_RESPONSE_BYTES = 2_000_000
MAX_CRAWL_PAGES = 1000
PAGE_DELAY_SECONDS = 0.25


def fetch_page(cursor=None, limit=100, *, opener=urlopen, pause=time.sleep):
    """Read-only registry page with bounded, polite transient HTTP retries."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be integer in 1..100')
    if cursor is not None and (not isinstance(cursor, str) or not cursor.strip()):
        raise ValueError('invalid cursor')
    params = {'limit': limit, 'version': 'latest'}
    if cursor:
        params['cursor'] = cursor
    req = Request(BASE + '?' + urlencode(params), headers={
        'User-Agent': 'AgentMine-research/0.1', 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with opener(req, timeout=25) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError('registry response exceeds maximum size')
            return json.loads(data)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            header = exc.headers.get('Retry-After') if exc.headers else None
            if header is not None:
                # Fail closed rather than retry early when the server asks us
                # to wait longer than this bounded synchronous collector can.
                try:
                    seconds = int(header)
                except (ValueError, TypeError):
                    raise
                if seconds < 0 or seconds > 30:
                    raise
                pause(max(2 ** attempt, seconds))
            else:
                pause(2 ** attempt)
    raise RuntimeError('unreachable')

def collect_snapshot(max_pages=3, fetch=fetch_page, *, page_delay_seconds=PAGE_DELAY_SECONDS, pause=time.sleep):
    """Return raw pages, unique listings, and pagination completeness.

    A bounded inter-page delay protects the public registry during large crawls.
    Inject `pause` for deterministic offline tests; no network calls in tests.
    """
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_CRAWL_PAGES:
        raise ValueError("max_pages must be an integer in 1..1000")
    if (type(page_delay_seconds) not in (int, float)
            or not math.isfinite(page_delay_seconds)
            or not 0 <= page_delay_seconds <= 10):
        raise ValueError("page_delay_seconds must be finite in 0..10")
    seen_items = set()
    seen_cursors = set()
    pages, items = [], []
    cursor = None
    for page_index in range(max_pages):
        if cursor in seen_cursors:
            raise ValueError("registry pagination cursor cycle")
        seen_cursors.add(cursor)
        if page_index and page_delay_seconds:
            pause(page_delay_seconds)
        page = fetch(cursor)
        if not isinstance(page, dict) or not isinstance(page.get("servers"), list):
            raise ValueError("registry response missing servers list")
        # Missing pagination metadata cannot establish that the crawl ended.
        # Do not turn a truncated/changed API response into a complete census.
        metadata = page.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("registry response missing pagination metadata")
        # The official API defines metadata.count as the number of rows on
        # this page, not the number of unique names or total registry size.
        # A contradictory count means the page cannot support a census.
        if "count" in metadata:
            count = metadata["count"]
            if type(count) is not int or count != len(page["servers"]):
                raise ValueError("registry page count disagrees with servers list")
        pages.append(page)
        for item in page["servers"]:
            if not isinstance(item, dict):
                raise ValueError("invalid registry listing")
            server = item.get("server", item)
            if not isinstance(server, dict):
                raise ValueError("invalid registry server")
            name, version = server.get("name"), server.get("version")
            # A successful page count is not evidence of a complete census
            # if individual rows are silently discarded for missing identity.
            # The official Registry server schema requires name and version.
            if not isinstance(name, str) or not name.strip():
                raise ValueError("registry server missing name")
            if not isinstance(version, str) or not version.strip():
                raise ValueError("registry server missing version")
            key = (name.strip(), version)
            if key in seen_items:
                continue
            seen_items.add(key)
            items.append(item)
        next_cursor = metadata.get("nextCursor")
        if next_cursor is None or next_cursor == "":
            return pages, items, {"complete": True, "next_cursor": None, "pages_fetched": len(pages)}
        if not isinstance(next_cursor, str) or not next_cursor.strip():
            raise ValueError("invalid registry cursor")
        if next_cursor in seen_cursors:
            raise ValueError("registry pagination cursor cycle")
        cursor = next_cursor
    return pages, items, {"complete": False, "next_cursor": cursor, "pages_fetched": len(pages)}


def collect_with_provenance(max_pages=3, fetch=fetch_page):
    """Backward-compatible (raw_pages, unique_listings) interface."""
    pages, items, _ = collect_snapshot(max_pages, fetch)
    return pages, items

def collect(max_pages=3, fetch=fetch_page):
    """Backward-compatible listings-only interface."""
    return collect_with_provenance(max_pages, fetch)[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output", default="data/mcp_registry_snapshot.json")
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_pages > MAX_CRAWL_PAGES:
        parser.error("--max-pages must be between 1 and 1000")
    pages, rows, pagination = collect_snapshot(args.max_pages)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    observed = datetime.now(timezone.utc)
    stamp = observed.strftime("%Y%m%dT%H%M%S%fZ")
    raw_path = path.with_name(f"{path.stem}_raw_{stamp}{path.suffix}")
    raw_payload = {"observed_at": observed.isoformat(), "source": BASE, "pages": pages}
    raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = {
        "observed_at": observed.isoformat(), "source": BASE,
        "raw_snapshot": raw_path.name, "count": len(rows), "records": rows,
        "pagination": pagination,
        "note": "Registry listings indicate supply, not purchases or active users."
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} unique listings to {path}; raw pages in {raw_path}")


if __name__ == "__main__":
    main()
