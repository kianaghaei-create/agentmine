"""Local, minimal partner QA against the historical official TED reference.

No network, competitor content, customer identities or tender text. Input is
either a labeled synthetic demo or a locally authorized minimal projection.
A match is against published Search metadata, never a legal or live cutoff.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from time import perf_counter
from zoneinfo import ZoneInfo

from src.ted_lifecycle_chronology import _publication_id, _valid_offset
from src.ted_official_reference_feed import from_root

REFERENCE_TYPE = "historical_official_only_TED_reference_not_legal_or_customer_outcome"
BATCH_KEYS = {"sample_kind", "permission_confirmed", "observed_at_utc", "rows"}
ROW_KEYS = {"publication_number", "scope", "stage", "deadline"}
SCOPES = {"notice_version", "procedure_snapshot"}
STAGES = {"tender", "participation"}
UTC_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLOCK = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?P<seconds>:\d{2})?(?P<offset>Z|[+-]\d{2}:\d{2})?$")
STOCKHOLM = ZoneInfo("Europe/Stockholm")
MAX_ROWS = 1000
MAX_INPUT_BYTES = 1_000_000


def _validate_clock(value, has_seconds):
    # Reject day rollover and overflow independently of Python's parser.
    if (int(value[11:13]) > 23 or int(value[14:16]) > 59
            or (has_seconds and int(value[17:19]) > 59)):
        raise ValueError("clock outside 00:00..23:59:59")


def _parse_utc(value):
    if not isinstance(value, str) or not UTC_STAMP.fullmatch(value):
        raise ValueError("observation/source timestamp must be explicit UTC")
    _validate_clock(value, True)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_deadline(value):
    if value is None:
        return None, None
    if not isinstance(value, str):
        raise ValueError("deadline must be ISO date/time text or null")
    if DATE.fullmatch(value):
        return "date", datetime.fromisoformat(value).date()
    match = CLOCK.fullmatch(value)
    if not match:
        raise ValueError("deadline must be ISO date, minute or second precision")
    _validate_clock(value, bool(match["seconds"]))
    if match["offset"] and not _valid_offset(match["offset"]):
        raise ValueError("deadline offset outside supported timezone range")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    precision = "second" if match["seconds"] else "minute"
    return ("aware_" if match["offset"] else "naive_") + precision, instant


def _clock_equal(value, expected, precision):
    if precision.endswith("minute"):
        value = value.replace(second=0, microsecond=0)
        expected = expected.replace(second=0, microsecond=0)
    return value == expected


def _compare_deadline(kind, value, expected):
    local = expected.astimezone(STOCKHOLM)
    if kind == "date":
        return ("context_only", "date_compatible_not_instant") if value in (
            expected.date(), local.date()) else ("review", "date_outside_utc_stockholm")
    if kind.startswith("naive_"):
        clocks = (expected.replace(tzinfo=None), local.replace(tzinfo=None))
        if any(_clock_equal(value, clock, kind) for clock in clocks):
            return "context_only", "offsetless_clock_compatible_not_instant"
        return "review", "offsetless_clock_outside_utc_stockholm"
    actual = value.astimezone(timezone.utc)
    if not _clock_equal(actual, expected, kind):
        return "review", "offset_aware_deadline_discrepancy"
    if kind == "aware_minute":
        return "context_only", "minute_compatible_not_exact_second"
    return "exact_match", "exact_published_instant"


def _publication_interval(start, end, source_observed):
    start, end = _parse_utc(start), _parse_utc(end)
    if end - start != timedelta(days=1) or end > source_observed:
        raise ValueError("invalid or incomplete historical publication interval")
    return start, end


def _reference_index(reference):
    if (reference.get("evidence_type") != REFERENCE_TYPE
            or reference.get("fixed_notice_count") != 20
            or len(reference.get("records", [])) != 20):
        raise ValueError("official frozen reference required")
    source = reference["source"]
    source_observed = _parse_utc(source["source_observed_at_utc"])
    index = {}
    for row in reference["records"]:
        number = _publication_id(row["publication_number"])
        if (number in index or row["published_stage"] not in STAGES
                or row["operative_deadline_verified"] is not False):
            raise ValueError("invalid official reference record")
        instant = _parse_utc(row["published_deadline_utc"])
        start, end = _publication_interval(row["publication_day_start_utc"],
                                           row["publication_day_end_exclusive_utc"],
                                           source_observed)
        index[number] = (row["published_stage"], instant, start, end)
    frozen = set(index)
    prior_to_change, change_to_prior = {}, {}
    for change in reference["linked_change_metadata"]:
        if change["status"] != "linked_uniform_same_stage_metadata":
            continue
        prior = _publication_id(change["prior_publication_number"])
        latest = _publication_id(change["change_publication_number"])
        old = _parse_utc(change["prior_deadline_utc"])
        new = _parse_utc(change["new_deadline_utc"])
        stage = change["stage"]
        start, end = _publication_interval(change["prior_publication_day_start_utc"],
                                           change["prior_publication_day_end_exclusive_utc"],
                                           source_observed)
        if (prior in index or latest not in frozen or latest in change_to_prior
                or index[latest][:2] != (stage, new)
                or end > index[latest][2]
                or (new - old).total_seconds() != change["deadline_change_seconds"]):
            raise ValueError("unresolved or inconsistent linked reference")
        index[prior] = (stage, old, start, end)
        prior_to_change[prior] = latest
        change_to_prior[latest] = prior
    return index, frozen, prior_to_change, change_to_prior, source_observed


def _as_of_target(number, scope, observed, source_observed, index, prior_to_change):
    """Select only a publication-day-compatible historical reference.

    The exact time within a publication day is unknown. Procedure snapshots
    after the reference observation cannot be judged as current from this
    frozen source. Notice-version comparisons remain historical, not live.
    """
    if number not in index:
        return None, "outside_reference"
    start, end = index[number][2:]
    if observed < start:
        return None, "observation_before_notice_publication_day"
    if observed < end:
        return None, "notice_publication_time_unknown"
    if scope == "notice_version":
        return number, None
    if observed > source_observed:
        return None, "procedure_snapshot_after_reference_observation"
    latest = prior_to_change.get(number)
    if latest:
        change_start, change_end = index[latest][2:]
        if observed < change_start:
            return number, None
        if observed < change_end:
            return None, "change_publication_time_unknown"
        return latest, None
    return number, None


def compare(batch, reference):
    """Compare a minimal local projection; never return its raw stage/clock."""
    if not isinstance(batch, dict) or set(batch) != BATCH_KEYS:
        raise ValueError("unexpected batch fields; no identities or tender text")
    kind = batch["sample_kind"]
    if kind not in ("synthetic_fixture", "authorized_partner_local"):
        raise ValueError("explicit sample kind required")
    if batch["permission_confirmed"] is not (kind == "authorized_partner_local"):
        raise ValueError("authorized local input requires explicit permission; demo is synthetic")
    observed = _parse_utc(batch["observed_at_utc"])
    rows = batch["rows"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("input must contain 1 to 1000 rows")
    index, frozen, prior_to_change, change_to_prior, source_observed = _reference_index(reference)
    seen, covered, results = set(), set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise ValueError("unexpected row fields; no identities or tender text")
        number = _publication_id(row["publication_number"])
        scope, stage = row["scope"], row["stage"]
        if not isinstance(scope, str) or scope not in SCOPES:
            raise ValueError("explicit notice_version or procedure_snapshot scope required")
        if stage is not None and (not isinstance(stage, str) or stage not in STAGES):
            raise ValueError("stage must be tender, participation or null")
        if (number, scope) in seen:
            raise ValueError("duplicate publication/scope row")
        seen.add((number, scope))
        precision, value = _parse_deadline(row["deadline"])
        target, unknown_code = _as_of_target(number, scope, observed, source_observed,
                                             index, prior_to_change)
        item = {"publication_number": number, "scope": scope,
                "reference_publication_number": None, "reference_stage": None,
                "reference_deadline_utc": None, "reference_notice_link": None,
                "reference_basis": None, "status": "unknown", "code": "outside_reference"}
        if target is None:
            item["code"] = unknown_code
            results.append(item)
            continue
        expected_stage, expected, _, _ = index[target]
        if target in frozen:
            covered.add(target)
        linked = scope == "procedure_snapshot" and target in change_to_prior
        prior_as_of = scope == "procedure_snapshot" and target in prior_to_change
        item.update({"reference_publication_number": target,
                     "reference_stage": expected_stage,
                     "reference_deadline_utc": expected.isoformat().replace("+00:00", "Z"),
                     "reference_notice_link": "https://ted.europa.eu/en/notice/" + target + "/html",
                     "reference_basis": ("linked_change_snapshot" if linked else
                                         "linked_prior_before_change_publication_day" if prior_as_of else
                                         "published_notice_version")})
        if stage is None:
            status, code = "review", "stage_missing"
        elif stage != expected_stage:
            status, code = "review", "stage_discrepancy_deadline_not_compared"
        elif precision is None:
            status, code = "review", "deadline_missing"
        else:
            status, code = _compare_deadline(precision, value, expected)
            if linked and status == "review":
                old = index[change_to_prior[target]][1]
                old_status, _ = _compare_deadline(precision, value, old)
                if old_status in ("exact_match", "context_only"):
                    code = "linked_prior_deadline_compatible"
        item.update(status=status, code=code)
        results.append(item)
    counts = Counter(r["status"] for r in results)
    return {
        "evidence_type": "local_reference_comparison_not_legal_or_customer_outcome",
        "sample_kind": kind,
        "source_observed_at_utc": reference["source"]["source_observed_at_utc"],
        "input_observed_at_utc": batch["observed_at_utc"],
        "source_attribution": reference["source"]["attribution"],
        "input_row_count": len(rows),
        "distinct_frozen_references_covered": len(covered),
        "frozen_reference_count": len(frozen),
        "unobserved_frozen_reference_count": len(frozen - covered),
        "status_counts": {key: counts[key] for key in
                          ("exact_match", "context_only", "review", "unknown")},
        "items": results,
        "new_source_requests": 0,
        "verified_legal_errors": None,
        "verified_supplier_outcomes": None,
        "verified_agentmine_revenue": None,
        "actual_variable_cost_sek": None,
        "warning": ("Historical official Search metadata only. Scope is explicit; "
                    "a linked change is not a complete amendment history. Publication-day "
                    "timing is bounded, not exact; pre-publication and ambiguous same-day "
                    "comparisons remain unknown. Procedure snapshots after the reference "
                    "observation remain unknown. Date/minute/offsetless compatibility is "
                    "not an exact instant. Unknown or unobserved "
                    "rows are not errors. Permission is self-declared, not independently "
                    "verified. Synthetic rows are not customer evidence. No live alert, "
                    "legal cutoff, customer savings, WTP or delivery-cost claim."),
    }


def demo_batch(reference):
    """Use all 20 real reference IDs with seven labeled synthetic mutations."""
    rows = [{"publication_number": r["publication_number"], "scope": "notice_version",
             "stage": r["published_stage"], "deadline": r["published_deadline_utc"]}
            for r in reference["records"]]
    changes = {
        "603727-2026": {"deadline": None},
        "605974-2026": {"deadline": "2026-10-05"},
        "611111-2026": {"deadline": "2026-10-06T21:59"},
        "601453-2026": {"scope": "procedure_snapshot", "deadline": "2026-08-31"},
        "612139-2026": {"deadline": "2026-09-29"},
        "609559-2026": {"stage": "tender"},
        "601656-2026": {"deadline": "2026-09-29T23:59+02:00"},
    }
    for row in rows:
        row.update(changes.get(row["publication_number"], {}))
    return {"sample_kind": "synthetic_fixture", "permission_confirmed": False,
            "observed_at_utc": reference["source"]["source_observed_at_utc"], "rows": rows}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def read_batch(path):
    with path.open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds local size limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true")
    mode.add_argument("--input", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--repeat", type=int, default=1,
                        help="bounded synthetic demo comparison timing only")
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= 1000 or (args.repeat != 1 and not args.demo):
        parser.error("repeat must be 1..1000 and is only for the synthetic demo")
    reference = from_root(args.root)
    batch = demo_batch(reference) if args.demo else read_batch(args.input)
    start = perf_counter()
    for _ in range(args.repeat):
        report = compare(batch, reference)
    elapsed = perf_counter() - start
    if args.demo and args.repeat > 1:
        report["local_compute_benchmark"] = {
            "iterations": args.repeat, "row_comparisons": args.repeat * len(batch["rows"]),
            "elapsed_seconds": round(elapsed, 6),
            "scope": "in-memory comparison only; excludes ingestion, network, support and money",
        }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
