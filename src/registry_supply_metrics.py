"""Measure MCP Registry supply, never customers, usage or payment.

Reads snapshots from src.collect_mcp_registry. A publisher namespace is an
unverified label, not a legal supplier. No network or external writes.
"""
from collections import Counter
from datetime import datetime


def analyze_snapshot(snapshot):
    """Summarize server names and namespace labels in one timestamped crawl."""
    if not isinstance(snapshot, dict):
        raise ValueError("expected snapshot object")
    observed = snapshot.get("observed_at")
    if not isinstance(observed, str):
        raise ValueError("missing observed_at")
    try:
        timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("observed_at must have timezone")
    source = snapshot.get("source")
    if not isinstance(source, str) or not source.startswith("https://"):
        raise ValueError("missing HTTPS source provenance")
    records = snapshot.get("records")
    pagination = snapshot.get("pagination")
    if not isinstance(records, list) or not isinstance(pagination, dict):
        raise ValueError("expected records and pagination")
    complete = pagination.get("complete")
    pages = pagination.get("pages_fetched")
    if type(complete) is not bool or type(pages) is not int or pages < 1:
        raise ValueError("invalid pagination metadata")
    cursor = pagination.get("next_cursor")
    if complete:
        if cursor is not None:
            raise ValueError("complete crawl cannot have next_cursor")
    elif not isinstance(cursor, str) or not cursor.strip():
        raise ValueError("partial snapshot must preserve next_cursor")
    seen = set()
    invalid = 0
    duplicates = 0
    namespaces = Counter()
    unknown_namespace = 0
    for row in records:
        if not isinstance(row, dict):
            invalid += 1
            continue
        server = row.get("server", row)
        name = server.get("name") if isinstance(server, dict) else None
        if not isinstance(name, str) or not name.strip():
            invalid += 1
            continue
        name = name.strip()
        if name in seen:
            duplicates += 1
            continue
        seen.add(name)
        if "/" not in name or not name.split("/", 1)[0].strip():
            unknown_namespace += 1
            continue
        namespaces[name.split("/", 1)[0]] += 1
    known = sum(namespaces.values())
    hhi = sum((n / known) ** 2 for n in namespaces.values()) if known else None
    largest = max(namespaces.values()) / known if known else None
    full_hhi_eligible = complete and invalid == 0 and unknown_namespace == 0 and known > 0
    return {
        "observed_at": observed,
        "source": source,
        "crawl_complete": complete,
        "scope": "complete_registry_crawl_reported" if complete else "partial_registry_sample_only",
        "pages_fetched": pages,
        "listing_rows": len(records),
        "distinct_server_names": len(seen),
        "duplicate_name_rows": duplicates,
        "invalid_name_rows": invalid,
        "distinct_publisher_namespace_labels": len(namespaces),
        "server_names_with_unknown_namespace": unknown_namespace,
        "namespace_label_coverage": known / len(seen) if seen else None,
        "sample_largest_namespace_share": largest,
        "sample_namespace_hhi": hhi,
        "complete_registry_namespace_hhi": hhi if full_hhi_eligible else None,
        "complete_registry_hhi_suppression_reason": (
            None if full_hhi_eligible else
            "incomplete_crawl" if not complete else
            "invalid_name_rows" if invalid else
            "unknown_namespace_labels" if unknown_namespace else
            "no_valid_namespace_labels"
        ),
        "verified_supplier_businesses": None,
        "verified_paying_customers": None,
        "revenue_usd": None,
        "caveat": "Namespace labels are not verified businesses; server listings are not purchases. "
                  "Even a complete registry crawl does not cover the entire agent market. "
                  "Completeness is collector-reported, not independently audited. "
                  "Sample HHI is conditional on recognized namespace labels.",
    }


def main():
    """Analyze saved collector JSON; no network or external writes."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Saved JSON from collect_mcp_registry.py")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(analyze_snapshot(data), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
