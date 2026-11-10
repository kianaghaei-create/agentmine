"""Audit chronology in the frozen TED lifecycle Search metadata.

Publication dates are day intervals, not exact publication times. A uniform
notice-level deadline is derived only when every projected date and every
projected time agree, with equal cardinality and matching offsets. No lot
arrays are joined. The output is metadata evidence, not a legal cutoff,
complete amendment history, award date, supplier harm or realized spend.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from uuid import UUID

SNAPSHOT_PATH = "data/evidence/ted_fixed20_lifecycle_metadata_2026-11-10.json"
COHORT_PATH = "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json"
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})(Z|[+-]\d{2}:\d{2})$")
TIME = re.compile(r"^(\d{2}:\d{2}:\d{2})(Z|[+-]\d{2}:\d{2})$")
STAGES = (
    ("tender", "deadline-receipt-tender-date-lot", "deadline-receipt-tender-time-lot"),
    ("participation", "deadline-receipt-request-date-lot", "deadline-receipt-request-time-lot"),
)


def _publication_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,8}-20[0-9]{2}", value):
        raise ValueError("invalid publication number")
    number, year = value.split("-")
    if int(number) == 0:
        raise ValueError("zero publication number")
    return f"{int(number)}-{year}"


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("missing UUID")
    try:
        parsed = str(UUID(value))
    except ValueError as exc:
        raise ValueError("invalid UUID") from exc
    if parsed != value.lower():
        raise ValueError("noncanonical UUID")
    return parsed


def _version(value):
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,2}", str(value)) or int(value) < 1:
        raise ValueError("invalid notice version")
    return f"{int(value):02d}"


def _valid_offset(value):
    if value == "Z":
        return True
    hours, minutes = map(int, value[1:].split(":"))
    return hours <= 14 and minutes <= 59 and (hours < 14 or minutes == 0)


def _offset(value):
    return "+00:00" if value == "Z" else value


def _iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _seconds(value):
    return int(value.total_seconds())


def _publication_day(value):
    match = DATE.fullmatch(value) if isinstance(value, str) else None
    if not match or not _valid_offset(match[2]):
        raise ValueError("publication date lacks valid explicit offset")
    start = datetime.fromisoformat(match[1] + "T00:00:00" + _offset(match[2]))
    return start, start + timedelta(days=1)


def _uniform_deadline(row):
    present = [(stage, row.get(df), row.get(tf)) for stage, df, tf in STAGES
               if df in row or tf in row]
    if len(present) != 1:
        return None, None, "missing_or_multiple_stages"
    stage, dates, times = present[0]
    if (not isinstance(dates, list) or not isinstance(times, list) or not dates
            or len(dates) != len(times) or not all(isinstance(v, str) for v in dates + times)):
        return stage, None, "missing_or_unbalanced_projection"
    # Identical values across each projection permit a notice-level statement
    # without assuming a position-wise lot join. Mixed values remain unresolved.
    if len(set(dates)) != 1 or len(set(times)) != 1:
        return stage, None, "nonuniform_projection"
    dm, tm = DATE.fullmatch(dates[0]), TIME.fullmatch(times[0])
    if (not dm or not tm or not _valid_offset(dm[2]) or not _valid_offset(tm[2])
            or _offset(dm[2]) != _offset(tm[2])):
        return stage, None, "invalid_or_conflicting_offsets"
    hour, minute, second = map(int, tm[1].split(":"))
    if hour > 23 or minute > 59 or second > 59:
        return stage, None, "invalid_deadline"
    try:
        instant = datetime.fromisoformat(dm[1] + "T" + tm[1] + _offset(tm[2]))
    except ValueError:
        return stage, None, "invalid_deadline"
    return stage, instant, "uniform_notice_level_metadata"


def _relation(instant, start, end):
    if instant < start:
        return "before_publication_day"
    if instant < end:
        return "within_publication_day"
    return "after_publication_day"


def audit(snapshot, cohort):
    """Return a source-bound chronology audit of the exact frozen cohort."""
    if (not isinstance(cohort, dict) or cohort.get("complete_frame_reconciled") is not True
            or cohort.get("cohort_size") != 20 or not isinstance(cohort.get("notice_items"), list)
            or len(cohort["notice_items"]) != 20):
        raise ValueError("frozen reconciled 20-notice cohort required")
    frozen = [_publication_id(r["publication_number"]) for r in cohort["notice_items"]]
    if len(set(frozen)) != 20:
        raise ValueError("duplicate frozen publication")
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("rows"), list)
            or not isinstance(snapshot.get("summary"), dict)):
        raise ValueError("lifecycle snapshot required")
    rows = snapshot["rows"]
    summary = snapshot["summary"]
    if (summary.get("frozen_notice_ids") != 20 or summary.get("frozen_ids_with_metadata") != 20
            or summary.get("frozen_rows_identical_across_queries") != 20
            or summary.get("procedure_query_notices") != len(rows)):
        raise ValueError("incomplete or inconsistent lifecycle snapshot")
    by_id, by_version, procedures = {}, {}, {}
    for row in rows:
        number = _publication_id(row["publication-number"])
        procedure = _uuid(row["procedure-identifier"])
        key = (_uuid(row["notice-identifier"]), _version(row["notice-version"]))
        if number in by_id or key in by_version:
            raise ValueError("duplicate publication or notice version")
        by_id[number] = row
        by_version[key] = number
        procedures.setdefault(procedure, []).append(number)
    if not set(frozen).issubset(by_id):
        raise ValueError("missing frozen publication")
    frozen_procedures = {_uuid(by_id[n]["procedure-identifier"]) for n in frozen}
    if set(procedures) != frozen_procedures or summary.get("distinct_procedure_ids") != len(procedures):
        raise ValueError("unbound or inconsistent procedure population")

    deadline_rows = []
    for number in frozen:
        row = by_id[number]
        stage, instant, status = _uniform_deadline(row)
        start, end = _publication_day(row["publication-date"])
        deadline_rows.append({"publication_number": number, "stage": stage, "status": status,
                              "deadline_utc": _iso(instant) if instant else None,
                              "publication_day_start_utc": _iso(start),
                              "publication_day_end_exclusive_utc": _iso(end),
                              "deadline_vs_publication_day": _relation(instant, start, end) if instant else None})

    changes = []
    for number, row in by_id.items():
        reference = row.get("change-notice-version-identifier")
        if not reference:
            continue
        item = {"change_publication_number": number, "reference": reference,
                "prior_publication_number": None, "status": "unresolved_reference"}
        changes.append(item)
        if not isinstance(reference, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}-[0-9]{2}", reference):
            continue
        try:
            prior_key = (_uuid(reference[:-3]), _version(reference[-2:]))
        except ValueError:
            continue
        prior_number = by_version.get(prior_key)
        if not prior_number or prior_number == number:
            continue
        prior = by_id[prior_number]
        if _uuid(prior["procedure-identifier"]) != _uuid(row["procedure-identifier"]):
            item["status"] = "reference_outside_procedure"
            continue
        item["prior_publication_number"] = prior_number
        old_stage, old, old_status = _uniform_deadline(prior)
        new_stage, new, new_status = _uniform_deadline(row)
        item.update({"prior_deadline_status": old_status, "new_deadline_status": new_status})
        if not old or not new or old_stage != new_stage:
            item["status"] = "deadline_comparison_unresolved"
            continue
        start, end = _publication_day(row["publication-date"])
        item.update({"status": "linked_uniform_same_stage_metadata", "stage": new_stage,
                     "prior_deadline_utc": _iso(old), "new_deadline_utc": _iso(new),
                     "deadline_change_seconds": _seconds(new - old),
                     "change_publication_day_start_utc": _iso(start),
                     "change_publication_day_end_exclusive_utc": _iso(end),
                     "prior_deadline_vs_change_publication_day": _relation(old, start, end),
                     "new_deadline_vs_change_publication_day": _relation(new, start, end),
                     "seconds_from_prior_deadline_to_change_publication_day_start": _seconds(start - old)})

    results = []
    for number, row in by_id.items():
        if row.get("form-type") != "result":
            continue
        procedure = _uuid(row["procedure-identifier"])
        competition = [n for n in procedures[procedure] if by_id[n].get("form-type") == "competition"]
        item = {"result_publication_number": number, "competition_publication_numbers": sorted(competition),
                "status": "ambiguous_competition_history"}
        results.append(item)
        # Do not silently choose a version from a multi-notice history.
        if len(competition) != 1:
            continue
        stage, deadline, status = _uniform_deadline(by_id[competition[0]])
        if not deadline or stage != "tender":
            item["status"] = "tender_deadline_unresolved"
            continue
        start, end = _publication_day(row["publication-date"])
        item.update({"status": "single_competition_uniform_tender_metadata",
                     "tender_deadline_utc": _iso(deadline),
                     "result_publication_day_start_utc": _iso(start),
                     "result_publication_day_end_exclusive_utc": _iso(end),
                     "seconds_from_deadline_to_publication_day_start": _seconds(start - deadline),
                     "seconds_from_deadline_to_publication_day_end_exclusive": _seconds(end - deadline)})

    return {"evidence_type": "TED_Search_metadata_chronology_not_legal_or_exact_publication_time",
            "source_snapshot": SNAPSHOT_PATH, "source_observed_at": snapshot.get("observed_at"),
            "frozen_notice_count": len(frozen), "lifecycle_notice_count": len(rows),
            "uniform_frozen_deadline_count": sum(r["deadline_utc"] is not None for r in deadline_rows),
            "frozen_deadlines_before_own_publication_day": sum(r["deadline_vs_publication_day"] == "before_publication_day" for r in deadline_rows),
            "linked_change_comparisons": sum(r["status"] == "linked_uniform_same_stage_metadata" for r in changes),
            "linked_prior_deadlines_before_change_publication_day": sum(r.get("prior_deadline_vs_change_publication_day") == "before_publication_day" for r in changes),
            "result_publication_interval_comparisons": sum(r["status"] == "single_competition_uniform_tender_metadata" for r in results),
            "deadline_rows": deadline_rows, "change_rows": changes, "result_rows": results,
            "verified_legal_deadline_errors": None, "amendment_histories_cleared": 0,
            "verified_supplier_harm_or_savings": None, "verified_agentmine_revenue": None,
            "warning": "Publication date is a fixed-offset day interval, not an exact publication timestamp. A prior deadline before the change publication day is a chronology signal only: portal changes, dispatch, legal effect and supplier impact are unknown. Result publication is not award date or payment."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path(SNAPSHOT_PATH))
    parser.add_argument("--cohort", type=Path, default=Path(COHORT_PATH))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = audit(json.loads(args.snapshot.read_text(encoding="utf-8")),
                   json.loads(args.cohort.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
