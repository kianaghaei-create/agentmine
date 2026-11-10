"""Compare public Initask notice deadline visibility with the frozen TED-20.

This is a rendered-page, source-metadata audit, not a legal deadline check.
Unavailable pages are unknown. A clock shown without an offset is not an
instant. Reuse the existing lifecycle audit for identity and projection checks.
"""
import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from src.ted_lifecycle_chronology import audit as audit_lifecycle, SNAPSHOT_PATH, COHORT_PATH

EVIDENCE_PATH = "data/evidence/ted_fixed20_initask_stage_visibility_2026-11-10.json"
_KIND = "fixed20_initask_public_stage_visibility_not_legal_deadline"
_FIELDS = {"publication_number", "source_url", "retrieval_status",
           "displayed_stage", "displayed_minute", "displayed_offset",
           "lot_deadline_cells_empty"}
_MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
_STAGE_FIELDS = {
    "tender": ("deadline-receipt-tender-date-lot", "deadline-receipt-tender-time-lot"),
    "participation": ("deadline-receipt-request-date-lot", "deadline-receipt-request-time-lot"),
}


def audit(snapshot, cohort, evidence):
    lifecycle = audit_lifecycle(snapshot, cohort)
    if lifecycle["uniform_frozen_deadline_count"] != 20:
        raise ValueError("all frozen source deadlines must be uniform and resolved")
    if (not isinstance(evidence, dict) or evidence.get("evidence_type") != _KIND
            or evidence.get("source_snapshot") != SNAPSHOT_PATH
            or evidence.get("cohort_path") != COHORT_PATH
            or evidence.get("source_observed_at") != snapshot.get("observed_at")
            or evidence.get("source_publisher") != "Initask EU Tenders"):
        raise ValueError("unbound Initask evidence")
    try:
        observed = date.fromisoformat(evidence["observed_on"])
        source_day = datetime.fromisoformat(snapshot["observed_at"].replace("Z", "+00:00")).date()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("invalid observation date") from exc
    if observed < source_day:
        raise ValueError("display observation predates source snapshot")
    frozen = {r["publication_number"]: r for r in lifecycle["deadline_rows"]}
    official = {r["publication-number"]: r for r in snapshot["rows"]}
    rows = evidence.get("rows")
    if not isinstance(rows, list) or len(rows) != len(frozen):
        raise ValueError("retain every frozen ID, including unavailable pages")
    seen, results = set(), []
    counts = {stage: Counter() for stage in _STAGE_FIELDS}
    stockholm = ZoneInfo("Europe/Stockholm")
    for row in rows:
        if not isinstance(row, dict) or set(row) != _FIELDS:
            raise ValueError("unexpected display observation fields")
        number = row["publication_number"]
        if not isinstance(number, str) or number not in frozen or number in seen:
            raise ValueError("duplicate or outside frozen cohort")
        seen.add(number)
        if row["source_url"] != f"https://eutenders.initask.com/notice/{number}":
            raise ValueError("unbound public notice URL")
        source = frozen[number]
        stage = source["stage"]
        df, tf = _STAGE_FIELDS[stage]
        source_date, source_time = official[number][df][0], official[number][tf][0]
        source_minute = source_date[:10] + "T" + source_time[:5]
        source_offset = source_date[10:]
        source_utc = datetime.fromisoformat(source["deadline_utc"].replace("Z", "+00:00"))
        local_minute = source_utc.astimezone(stockholm).strftime("%Y-%m-%dT%H:%M")
        display = row["displayed_minute"]
        display_stage = row["displayed_stage"]
        status = row["retrieval_status"]
        c = counts[stage]
        c["attempted"] += 1
        item = {"publication_number": number, "source_stage": stage,
                "source_clock_minute": source_minute, "source_offset": source_offset,
                "source_stockholm_minute": local_minute, "source_deadline_utc": source["deadline_utc"],
                "displayed_minute": display, "displayed_stage": display_stage,
                "source_url": row["source_url"], "operative_deadline_verified": False}
        if status == "page_unavailable":
            if any(row[k] is not None for k in ("displayed_stage", "displayed_minute",
                                                "displayed_offset", "lot_deadline_cells_empty")):
                raise ValueError("unavailable page cannot assert display fields")
            c["unavailable"] += 1
            item["classification"] = "unavailable_unknown"
        elif status == "rendered":
            c["rendered"] += 1
            if row["displayed_offset"] is not None:
                raise ValueError("this evidence adapter only accepts offsetless rendered clocks")
            if display is None:
                if display_stage is not None or row["lot_deadline_cells_empty"] is not True:
                    raise ValueError("missing deadline requires empty main/lot deadline fields")
                c["no_deadline_visible"] += 1
                item["classification"] = "published_stage_deadline_not_visible"
            else:
                if (not isinstance(display, str) or not _MINUTE.fullmatch(display)
                        or display_stage not in _STAGE_FIELDS
                        or row["lot_deadline_cells_empty"] is not False):
                    raise ValueError("invalid rendered deadline")
                try:
                    datetime.fromisoformat(display)
                except ValueError as exc:
                    raise ValueError("invalid rendered clock") from exc
                c["deadline_visible"] += 1
                c["offset_not_visible"] += 1
                c["stage_matches"] += int(display_stage == stage)
                c["source_clock_matches"] += int(display == source_minute)
                c["stockholm_clock_matches"] += int(display == local_minute)
                utc_only = display == source_utc.strftime("%Y-%m-%dT%H:%M") and display != local_minute
                c["utc_clock_only_matches"] += int(utc_only)
                item.update({"classification": "offsetless_clock_displayed",
                             "stage_matches": display_stage == stage,
                             "source_clock_matches": display == source_minute,
                             "stockholm_clock_matches": display == local_minute,
                             "utc_clock_only_match": utc_only})
        else:
            raise ValueError("unknown retrieval status")
        results.append(item)
    keys = ("attempted", "rendered", "unavailable", "no_deadline_visible", "deadline_visible",
            "offset_not_visible", "stage_matches", "source_clock_matches",
            "stockholm_clock_matches", "utc_clock_only_matches")
    by_stage = {stage: {k: c[k] for k in keys} for stage, c in counts.items()}
    return {"evidence_type": _KIND, "observed_on": evidence["observed_on"],
            "source_observed_at": snapshot["observed_at"], "frozen_notice_count": len(frozen),
            "rendered_count": sum(c["rendered"] for c in counts.values()),
            "unavailable_count": sum(c["unavailable"] for c in counts.values()),
            "by_stage": by_stage, "items": results,
            "new_original_documents_inspected": 0, "new_portal_corroborations": 0,
            "verified_legal_deadline_errors": None, "verified_supplier_savings": None,
            "verified_agentmine_customers": None, "verified_agentmine_revenue": None,
            "warning": "Selected frozen cohort, not market prevalence. Missing public fields are not missing official deadlines. Offsetless minute clocks do not establish an instant, portal cutoff or legal error."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, default=Path(SNAPSHOT_PATH))
    p.add_argument("--cohort", type=Path, default=Path(COHORT_PATH))
    p.add_argument("--evidence", type=Path, default=Path(EVIDENCE_PATH))
    args = p.parse_args(argv)
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = audit(load(args.snapshot), load(args.cohort), load(args.evidence))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
