"""Read-only MCP registry collector with preserved raw-page provenance."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://registry.modelcontextprotocol.io/v0.1/servers"
MAX_RESPONSE_BYTES = 2_000_000


def fetch_page(cursor=None, limit=100):
    params = {"limit": limit, "version": "latest"}
    if cursor:
        params["cursor"] = cursor
    req = Request(BASE + "?" + urlencode(params), headers={
        "User-Agent": "AgentMine-research/0.1", "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("registry response exceeds maximum size")
    return json.loads(data)


def collect_with_provenance(max_pages=3, fetch=fetch_page):
    """Return (raw_pages, unique listings); listings are supply, not demand."""
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError("max_pages must be an integer in 1..100")
    seen_items = set()
    seen_cursors = set()
    pages, items = [], []
    cursor = None
    for _ in range(max_pages):
        if cursor in seen_cursors:
            raise ValueError("registry pagination cursor cycle")
        seen_cursors.add(cursor)
        page = fetch(cursor)
        if not isinstance(page, dict) or not isinstance(page.get("servers"), list):
            raise ValueError("registry response missing servers list")
        pages.append(page)
        for item in page["servers"]:
            if not isinstance(item, dict):
                raise ValueError("invalid registry listing")
            server = item.get("server", item)
            if not isinstance(server, dict):
                raise ValueError("invalid registry server")
            name, version = server.get("name"), server.get("version")
            if not isinstance(name, str) or not name.strip():
                continue
            key = (name.strip(), version)
            if key in seen_items:
                continue
            seen_items.add(key)
            items.append(item)
        metadata = page.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("invalid registry metadata")
        next_cursor = metadata.get("nextCursor")
        if not next_cursor:
            break
        if not isinstance(next_cursor, str):
            raise ValueError("invalid registry cursor")
        cursor = next_cursor
    return pages, items


def collect(max_pages=3, fetch=fetch_page):
    """Backward-compatible listings-only interface."""
    return collect_with_provenance(max_pages, fetch)[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output", default="data/mcp_registry_snapshot.json")
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_pages > 100:
        parser.error("--max-pages must be between 1 and 100")
    pages, rows = collect_with_provenance(args.max_pages)
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
        "note": "Registry listings indicate supply, not purchases or active users."
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} unique listings to {path}; raw pages in {raw_path}")


if __name__ == "__main__":
    main()
