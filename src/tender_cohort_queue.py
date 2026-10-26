"""Build a predeclared primary-source review queue from a complete TED snapshot.

Selection is reproducible, NOT a legal deadline check or a supplier demand metric.
The TED query defines the frame; this module does not validate query syntax.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

from src.ted_notice_evidence import ENDPOINT

_NOTICE = re.compile(r"^([1-9][0-9]{0,7})-(20[0-9]{2})$")


def _date(value):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, str):
        raise ValueError("missing or ambiguous publication-date")
    try:
        if re.fullmatch(r"[0-9]{8}", value):
            result = datetime.strptime(value, "%Y%m%d").date()
        elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[+-][0-9]{2}:[0-9]{2}", value):
            # TED publication-date may carry a UTC offset, e.g. 2026-09-17+02:00.
            # Preserve its local calendar date, rather than shifting to UTC.
            result = datetime.strptime(value, "%Y-%m-%d%z").date()
        else:
            result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid publication-date") from exc
    return result.isoformat()


def build_queue(snapshot, expected_query, *, count=20):
    """Select first N dated notices by (publication date, numeric notice ID).

    A partial search is not a census and must never silently become a
    'consecutive' cohort. The query must be fixed before interpreting rows.
    """
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError("count must be integer 1..100")
    if not isinstance(expected_query, str) or not expected_query.strip():
        raise ValueError("expected_query must be a nonempty TED query")
    if not isinstance(snapshot, dict) or snapshot.get("source_url") != ENDPOINT:
        raise ValueError("invalid TED snapshot source")
    if snapshot.get("query") != expected_query:
        raise ValueError("query mismatch; sampling frame must be predeclared")
    rows = snapshot.get("notices")
    if (snapshot.get("complete") is not True or not isinstance(rows, list)
            or type(snapshot.get("reported_total_notices")) is not int
            or snapshot["reported_total_notices"] != len(rows)
            or snapshot.get("unique_notices_collected") != len(rows)):
        raise ValueError("complete reconciled TED snapshot required")
    observed_at = snapshot.get("observed_at")
    if not isinstance(observed_at, str):
        raise ValueError("missing observed_at")
    try:
        stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("observed_at must be past offset-aware timestamp")
    keyed = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid TED notice row")
        publication = row.get("publication-number")
        match = _NOTICE.fullmatch(publication) if isinstance(publication, str) else None
        if not match or publication in seen:
            raise ValueError("invalid or duplicate publication-number")
        seen.add(publication)
        published = _date(row.get("publication-date"))
        keyed.append((published, int(match.group(1)), publication))
    if len(keyed) < count:
        raise ValueError("fewer notices than predeclared cohort count")
    chosen = sorted(keyed)[:count]
    return {
        "source_url": ENDPOINT,
        "observed_at": observed_at,
        "predeclared_query": expected_query,
        "selection_rule": "first N ascending publication-date then numeric publication-number in complete query result",
        "complete_query_population_notices": len(rows),
        "cohort_size": count,
        "primary_source_reviews_completed": 0,
        "items": [{
            "publication_number": publication,
            "publication_date": published,
            "notice_lookup_url": f"https://ted.europa.eu/en/notice/{publication}",
            "original_notice_stage": "not_reviewed",
            "submission_portal_stage": "not_reviewed",
            "amendments": "not_reviewed",
            "portal_access": "not_checked",
            "deadline_status": "unverified",
        } for published, _, publication in chosen],
        "verified_supplier_savings": None,
        "verified_paying_customers": None,
        "warning": "Queue only: TED query scope and individual CPV/country classification not independently checked; "
                   "notices are not unique procedures, legal deadlines, customer demand, awards or payments. "
                   "Primary notice, amendments and submission portal require manual review."
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--query", required=True, help="Exact query used in the input TED snapshot")
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    result = build_queue(json.loads(args.input.read_text(encoding="utf-8")), args.query, count=args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
