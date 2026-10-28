"""Offline triage of contradictory procurement deadline *displays*.

This is a review queue, not a legal deadline extractor. Dates for distinct
procurement stages must not be treated as comparable legal deadlines. Original
TED notices and submission portals require independent review before alerts.
"""
import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

_NOTICE = re.compile(r"^[1-9][0-9]{0,7}-20[0-9]{2}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")
_KINDS = {"official_summary", "third_party", "original_ted_notice",
          "submission_portal", "official_buyer_submission_portal",
          "third_party_summary", "third_party_republication_of_ted_notice_text"}
_STAGES = {"participation_request", "bid_submission", "questions", "unknown"}
# Caller-asserted source kinds, not independently authenticated authorities.
_PRIMARY_STAGE_SOURCES = {"original_ted_notice", "submission_portal",
                          "official_buyer_submission_portal"}
_LABELS = {"participation_deadline", "bid_deadline", "questions_deadline",
           "generic_deadline", "unknown"}
_STAGE_LABEL = {"participation_request": "participation_deadline",
                "bid_submission": "bid_deadline", "questions": "questions_deadline"}


def _parse_display(value):
    if not isinstance(value, str):
        raise ValueError("reported_deadline must be ISO date or offset-aware timestamp")
    if _DATE.fullmatch(value):
        try:
            return "date_label", date.fromisoformat(value).isoformat(), None
        except ValueError as exc:
            raise ValueError("invalid deadline date") from exc
    if _TIMESTAMP.fullmatch(value):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid deadline timestamp") from exc
        if dt.utcoffset() is None:
            raise ValueError("timestamp must include offset")
        return "offset_timestamp", dt.date().isoformat(), dt.astimezone(timezone.utc)
    raise ValueError("unsupported deadline display")


def _url(value, kind, publication_number):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("invalid source URL")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.fragment or parts.port not in (None, 443)):
        raise ValueError("source must be canonical HTTPS URL")
    if kind == "official_summary" and parts.hostname != "op.europa.eu":
        raise ValueError("official summary requires EU Publications Office host")
    if kind == "original_ted_notice":
        if parts.hostname != "ted.europa.eu":
            raise ValueError("original notice requires TED host")
        # A trusted host alone is not provenance: a TED page for a different
        # publication must not be promoted to an original for this cohort ID.
        expected = re.escape(publication_number)
        if (parts.query or not re.fullmatch(
                rf"/[a-z]{{2}}/notice/(?:-/detail/)?{expected}(?:/html)?/?",
                parts.path)):
            raise ValueError("original TED notice URL must match publication number")
    return value


def triage(evidence):
    """Classify source-display differences without claiming a legal cutoff."""
    if not isinstance(evidence, dict) or not _NOTICE.fullmatch(str(evidence.get("publication_number", ""))):
        raise ValueError("invalid publication number")
    rows = evidence.get("observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("at least one observation is required")
    seen = set()
    labels, kinds, formats = set(), set(), set()
    explicit_stages = defaultdict(set)
    date_only_by_stage = defaultdict(set)
    instants_by_stage = defaultdict(set)
    precision_by_stage = defaultdict(set)
    unknown_stage_dates = set()
    unknown_stage_instants = defaultdict(set)
    known_stage_instants_by_day = defaultdict(set)
    stage_label_reviews = []
    known_stage_dates = defaultdict(set)
    primary_stage_dates = defaultdict(set)
    unverified_explicit_stage_claims = []
    parsed = []
    for row in rows:
        if not isinstance(row, dict) or row.get("publication_number") != evidence["publication_number"]:
            raise ValueError("inconsistent notice observation")
        kind = row.get("source_kind")
        if kind not in _KINDS:
            raise ValueError("unknown source kind")
        url = _url(row.get("source_url"), kind, evidence["publication_number"])
        if url in seen:
            raise ValueError("duplicate source URL")
        seen.add(url)
        fmt, day, instant = _parse_display(row.get("reported_deadline"))
        stage = row.get("stage_claim", "unknown")
        label = row.get("display_label_claim", "unknown")
        if stage not in _STAGES or label not in _LABELS:
            raise ValueError("unknown procurement stage or deadline label")
        if stage == "unknown":
            unknown_stage_dates.add(day)
            if instant is not None:
                unknown_stage_instants[day].add(instant)
        else:
            explicit_stages[stage].add(day)
            precision_by_stage[stage].add(fmt)
            if instant is None:
                date_only_by_stage[stage].add(day)
            else:
                instants_by_stage[stage].add(instant)
                known_stage_instants_by_day[day].add(instant)
            known_stage_dates[day].add(stage)
            if kind in _PRIMARY_STAGE_SOURCES:
                primary_stage_dates[day].add(stage)
            else:
                unverified_explicit_stage_claims.append((url, day, stage))
            if label not in ("unknown", "generic_deadline", _STAGE_LABEL[stage]):
                stage_label_reviews.append(url)
        parsed.append((url, day, stage, label))
        labels.add(day)
        formats.add(fmt)
        kinds.add(kind)
    # A directory's explicit stage is still a directory claim. It cannot
    # validate itself against a conflicting original notice/submission portal.
    # This is review-only; source_kind itself is caller-asserted, not proof.
    for url, day, stage in unverified_explicit_stage_claims:
        if primary_stage_dates[day] and stage not in primary_stage_dates[day]:
            stage_label_reviews.append(url)
    # Two non-primary sources can each self-assert internally consistent but
    # contradictory stages for the same calendar date. Without a primary
    # stage observation, neither assertion establishes which stage is correct.
    # Queue both for review rather than silently reporting stage agreement.
    unverified_stage_sources_by_day = defaultdict(lambda: defaultdict(set))
    for url, day, stage in unverified_explicit_stage_claims:
        unverified_stage_sources_by_day[day][stage].add(url)
    for day, sources_by_stage in unverified_stage_sources_by_day.items():
        if len(sources_by_stage) > 1 and not primary_stage_dates[day]:
            for source_urls in sources_by_stage.values():
                stage_label_reviews.extend(source_urls)
    # Flag a generic label only if NONE of the known stages on that day
    # supports it. Several distinct stages can legitimately share a date;
    # one matching known stage prevents a false discrepancy.
    for url, day, stage, label in parsed:
        if (stage == "unknown" and label in ("bid_deadline", "participation_deadline")
                and known_stage_dates[day]
                and all(_STAGE_LABEL[known] != label for known in known_stage_dates[day])):
            stage_label_reviews.append(url)
    # Two independent directory displays can disagree about *which stage*
    # their identical date describes, even if neither source has an
    # independently verified stage. This is a review candidate only; it
    # cannot establish which directory is right or the legal deadline.
    unknown_specific_labels = defaultdict(set)
    unknown_specific_sources = defaultdict(set)
    for url, day, stage, label in parsed:
        if stage == "unknown" and label in ("bid_deadline", "participation_deadline",
                                              "questions_deadline"):
            unknown_specific_labels[day].add(label)
            unknown_specific_sources[day].add(url)
    for day, claimed in unknown_specific_labels.items():
        if len(claimed) > 1 and not known_stage_dates[day]:
            stage_label_reviews.extend(unknown_specific_sources[day])
    # An unknown-stage source with a different explicit time cannot establish
    # same-stage conflict, but must not be silently counted as agreement.
    unknown_stage_time_discrepancy = sorted(
        day for day, instants in unknown_stage_instants.items()
        if len(instants) > 1 or (
            bool(known_stage_instants_by_day[day])
            and any(instant not in known_stage_instants_by_day[day] for instant in instants)
        )
    )
    # Exact cutoff times are compared as UTC instants, not calendar labels.
    # Date-only claims cannot establish a matching hour or minute.
    same_stage_instant = sorted(stage for stage, instants in instants_by_stage.items() if len(instants) > 1)
    same_stage_date_only = sorted(stage for stage, dates in date_only_by_stage.items() if len(dates) > 1)
    same_stage = sorted(set(same_stage_instant) | set(same_stage_date_only))
    mixed_precision = sorted(stage for stage, precisions in precision_by_stage.items() if len(precisions) > 1)
    disagreement = len(labels) > 1
    timezone_equivalent = (disagreement and not unknown_stage_dates and not mixed_precision
                           and len(explicit_stages) == 1 and formats == {'offset_timestamp'}
                           and not same_stage and all(len(v) == 1 for v in instants_by_stage.values()))
    if same_stage:
        stage_status = "same_stage_display_conflict_needs_primary_review"
    elif unknown_stage_time_discrepancy:
        stage_status = "unknown_stage_time_discrepancy_needs_primary_review"
    elif disagreement and unknown_stage_dates:
        stage_status = "unknown_stage_discrepancy_needs_primary_review"
    elif mixed_precision:
        stage_status = "mixed_precision_requires_primary_review"
    elif timezone_equivalent:
        stage_status = "equivalent_utc_instant_different_calendar_labels"
    elif disagreement:
        stage_status = "different_stages_not_directly_comparable"
    elif stage_label_reviews:
        stage_status = "stage_label_requires_review"
    else:
        stage_status = "stage_consistent_displays_unverified"
    needs_review = bool(same_stage or mixed_precision or unknown_stage_time_discrepancy or stage_label_reviews or
                        (disagreement and not timezone_equivalent))
    return {
        "publication_number": evidence["publication_number"],
        "observation_count": len(rows),
        "distinct_display_calendar_dates": sorted(labels),
        "display_formats": sorted(formats),
        "source_kinds": sorted(kinds),
        "calendar_label_disagreement": disagreement,
        "same_stage_instant_conflict_stages": same_stage_instant,
        "unknown_stage_time_discrepancy_calendar_dates": unknown_stage_time_discrepancy,
        "mixed_precision_review_stages": mixed_precision,
        "triage_status": "manual_primary_source_review" if needs_review else "unverified_display_agreement",
        "explicit_stage_calendar_dates": {k: sorted(v) for k, v in sorted(explicit_stages.items())},
        "unknown_stage_calendar_dates": sorted(unknown_stage_dates),
        "same_stage_display_conflict_stages": same_stage,
        "stage_label_review_source_urls": sorted(set(stage_label_reviews)),
        "stage_aware_triage_status": stage_status,
        "original_ted_notice_present": "original_ted_notice" in kinds,
        "submission_portal_present": bool({"submission_portal", "official_buyer_submission_portal"} & kinds),
        "legal_deadline_verified": False,
        "authoritative_deadline": None,
        "verified_agentmine_customers": None,
        "warning": "Source displays are not verified legal deadlines. Date-only labels and offset timestamps "
                   "are not interchangeable; different procurement stages are not comparable. "
                   "Review original TED notice, amendments and live submission portal before supplier alerts. "
                   "This does not establish paying customer demand.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(triage(json.loads(args.input.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
