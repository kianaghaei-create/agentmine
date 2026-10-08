"""Read-only MCP registry snapshot collector; standard library only."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://registry.modelcontextprotocol.io/v0.1/servers"

def fetch_page(cursor=None, limit=100):
    params = {"limit": limit, "version": "latest"}
    if cursor:
        params["cursor"] = cursor
    req = Request(BASE + "?" + urlencode(params), headers={"User-Agent": "AgentMine-research/0.1", "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        return json.load(response)

def collect(max_pages=3, fetch=fetch_page):
    seen = set()
    items = []
    cursor = None
    for _ in range(max_pages):
        page = fetch(cursor)
        for item in page.get("servers", []):
            server = item.get("server", item)
            key = (server.get("name"), server.get("version"))
            if not key[0] or key in seen:
                continue
            seen.add(key)
            items.append(item)
        next_cursor = (page.get("metadata") or {}).get("nextCursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return items

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output", default="data/mcp_registry_snapshot.json")
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_pages > 100:
        parser.error("--max-pages must be between 1 and 100")
    rows = collect(args.max_pages)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"observed_at": datetime.now(timezone.utc).isoformat(), "source": BASE, "count": len(rows), "records": rows, "note": "Registry listings indicate supply, not purchases or active users."}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} unique listings to {path}")

if __name__ == "__main__":
    main()
