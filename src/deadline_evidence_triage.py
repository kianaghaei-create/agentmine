"""Offline triage of contradictory procurement deadline *displays*.

This is a review queue, not a legal deadline extractor. An official overview
can have no legal effect; the original TED notice and submission portal must
be independently reviewed before any supplier-facing alert. No network calls.
"""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

_NOTICE = re.compile(r"^[1-9][0-9]{0,7}-20[0-9]{2}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")
_KINDS = {"official_summary", "third_party", "original_ted_notice", "submission_portal"}


def _parse_display(value):
    if not isinstance(value, str):
        raise ValueError("reported_deadline must be ISO date or offset-aware timestamp")
    if _DATE.fullmatch(value):
        try:
            return "date_label", date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ValueError("invalid deadline date") from exc
    if _TIMESTAMP.fullmatch(value):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid deadline timestamp") from exc
        if dt.utcoffset() is None:
            raise ValueError("timestamp must include offset")
        return "offset_timestamp", dt.date().isoformat()
    raise ValueError("unsupported deadline display")


def _url(value, kind):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("invalid source URL")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.fragment or parts.port not in (None, 443)):
        raise ValueError("source must be canonical HTTPS URL")
    if kind == "official_summary" and parts.hostname != "op.europa.eu":
        raise ValueError("official summary requires EU Publications Office host")
    if kind == "original_ted_notice" and parts.hostname != "ted.europa.eu":
        raise ValueError("original notice requires TED host")
    return value


def triage(evidence):
    """Return conservative display-conflict metadata; never infer legal cutoff."""
    if not isinstance(evidence, dict) or not _NOTICE.fullmatch(str(evidence.get("publication_number", ""))):
        raise ValueError("invalid publication number")
    rows = evidence.get("observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("at least one observation is required")
    seen = set()
    labels, kinds, formats = set(), set(), set()
    for row in rows:
        if not isinstance(row, dict) or row.get("publication_number") != evidence["publication_number"]:
            raise ValueError("inconsistent notice observation")
        kind = row.get("source_kind")
        if kind not in _KINDS:
            raise ValueError("unknown source kind")
        url = _url(row.get("source_url"), kind)
        if url in seen:
            raise ValueError("duplicate source URL")
        seen.add(url)
        fmt, day = _parse_display(row.get("reported_deadline"))
        labels.add(day)
        formats.add(fmt)
        kinds.add(kind)
    disagreement = len(labels) > 1
    return {
        "publication_number": evidence["publication_number"],
        "observation_count": len(rows),
        "distinct_display_calendar_dates": sorted(labels),
        "display_formats": sorted(formats),
        "source_kinds": sorted(kinds),
        "calendar_label_disagreement": disagreement,
        "triage_status": "manual_primary_source_review" if disagreement else "unverified_display_agreement",
        "original_ted_notice_present": "original_ted_notice" in kinds,
        "submission_portal_present": "submission_portal" in kinds,
        "legal_deadline_verified": False,
        "authoritative_deadline": None,
        "verified_agentmine_customers": None,
        "warning": "Date-only labels and offset timestamps are not interchangeable legal cutoffs. "
                   "An official overview may lack legal effect. Review the original TED notice "
                   "and live submission portal before issuing any supplier-facing deadline alert. "
                   "These are source displays, not evidence of AgentMine buyer demand.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(triage(json.loads(args.input.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
