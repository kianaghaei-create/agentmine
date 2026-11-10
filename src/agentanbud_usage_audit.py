"""Audit aggregate Agentanbud publisher counters without inferring paid demand."""
from datetime import date
import json
from pathlib import Path
import re


_SOURCE = "https://agentanbud.se/analytics"
_SEGMENTS = frozenset({
    "other", "it_digital", "food", "health", "legal_consulting", "transport",
    "education", "construction", "cleaning_property", "energy_environment",
    "security", "furniture",
})


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _counts(values, name):
    if not isinstance(values, dict) or not values:
        raise ValueError(f"{name} must be a nonempty mapping")
    return {key: _count(value, name) for key, value in values.items()}


def _pct(numerator, denominator):
    return round(100 * numerator / denominator, 4) if denominator else None


def audit(snapshot):
    """Keep publisher scopes separate; a loop flag is not a buyer or fraud label."""
    if snapshot.get("source_url") != _SOURCE:
        raise ValueError("unexpected source")
    observed = snapshot.get("observed_on")
    if not isinstance(observed, str) or date.fromisoformat(observed).isoformat() != observed:
        raise ValueError("invalid observation date")
    revision = snapshot.get("publisher_code_sha")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("publisher code revision required")
    if snapshot.get("scope") != "default_retained_log_not_fixed_30d":
        raise ValueError("unexpected publisher scope")
    headline = _counts(snapshot["headline"], "headline")
    tools = _counts(snapshot["tool_counts"], "tool_counts")
    segments = _counts(snapshot["segment_counts"], "segment_counts")
    if set(segments) != _SEGMENTS:
        raise ValueError("expected fixed aggregate segment taxonomy")
    if any(not isinstance(k, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k) for k in tools):
        raise ValueError("invalid tool name")
    limit = _count(snapshot["tool_table_limit"], "tool_table_limit")
    if not limit or len(tools) > limit or "search_tenders" not in tools:
        raise ValueError("invalid tool table")
    retained = headline["retained_mcp_calls"]
    loop = headline["excluded_loop_calls"]
    reconstructed = retained + loop
    listed = sum(tools.values())
    complete = len(tools) < limit
    reconciles = listed == reconstructed if complete else None
    segment_total = sum(segments.values())
    web_rest = headline["web_searches"] + headline["rest_searches"]
    return {
        "observed_on": observed,
        "publisher_headline_reconstructed_mcp_calls": reconstructed,
        "publisher_retained_mcp_calls": retained,
        "publisher_excluded_loop_calls": loop,
        "publisher_loop_share_pct": _pct(loop, reconstructed) if reconciles else None,
        "publisher_retained_share_pct": _pct(retained, reconstructed) if reconciles else None,
        "listed_raw_tool_calls": listed,
        "tool_table_complete": complete,
        "tool_table_reconciles_with_headline": reconciles,
        "raw_search_tool_calls": tools["search_tenders"],
        "raw_nonsearch_tool_calls": listed - tools["search_tenders"] if complete else None,
        "raw_search_tool_share_pct": _pct(tools["search_tenders"], listed) if complete else None,
        "publisher_agent_identity_buckets_before_loop_filter": headline["agent_identity_buckets"],
        "publisher_mcp_handshakes": headline["mcp_handshakes"],
        "publisher_web_rest_searches": web_rest,
        "publisher_rest_share_of_web_rest_pct": _pct(headline["rest_searches"], web_rest),
        "raw_segment_event_total": segment_total,
        "raw_it_segment_events": segments["it_digital"],
        "raw_it_segment_share_pct": _pct(segments["it_digital"], segment_total),
        "raw_other_segment_share_pct": _pct(segments["other"], segment_total),
        "filtered_tool_mix": None,
        "verified_distinct_buyers": None,
        "verified_paid_demand": None,
        "verified_revenue": None,
        "warning": (
            "Publisher aggregate counters, not audited logs. The loop classifier and raw tool "
            "counter have different code filters; arithmetic reconciliation is not proof of "
            "a disjoint population. Identity buckets precede loop exclusion and can reset daily. "
            "Raw sector events include repeated queries. No unique buyers, payments, retention, "
            "actual costs or verified lost demand follow from these figures."
        ),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(audit(json.loads(Path(sys.argv[1]).read_text())), indent=2))
