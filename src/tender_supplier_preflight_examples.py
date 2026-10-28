"""Reproducible, historical supplier preflight examples from fixed TED evidence.

Select first three already inspected original notices with primary IT CPV 48/72,
by ascending publication number; accessible originals are not a random sample.

These are *not* actual supplier bid/no-bid decisions: no supplier capabilities,
operative amended deadlines, signed-in documents, or paid buyer responses exist.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path

from src.tender_primary_portal_stage_audit import audit

SELECTED = ("603727-2026", "606049-2026", "609559-2026")
FIELD_TO_STAGE = {"deadline-receipt-tender-date-lot": "tender",
                  "deadline-receipt-request-date-lot": "participation_request"}
ACTIONS = {
    "603727-2026": "REVIEW_QUALIFICATION_REQUIREMENTS",
    "606049-2026": "VERIFY_PARTICIPATION_STAGE_AND_MISSING_DIRECTORY_DATE",
    "609559-2026": "VERIFY_PARTICIPATION_STAGE_AND_PORTAL_ACCESS",
}


def _unique(rows):
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("publication_number"), str):
            raise ValueError("invalid row")
        number = row["publication_number"]
        if number in indexed:
            raise ValueError("duplicate publication number")
        indexed[number] = row
    return indexed


def build(cohort, official, directory, primary, *, as_of="2026-10-28"):
    try:
        day = date.fromisoformat(as_of)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid as_of date") from exc
    if day > datetime.now(timezone.utc).date():
        raise ValueError("future as_of date")
    if (cohort.get("complete_frame_reconciled") is not True
            or cohort.get("cohort_size") != 20
            or official.get("complete_current_query_frame") is not True
            or official.get("missing_cohort_count") != 0
            or cohort.get("query") != official.get("query")
            or directory.get("official_projection_observed_at_utc") != official.get("observed_at_utc")):
        raise ValueError("unreconciled cohort or evidence")
    fixed = _unique(cohort.get("notice_items"))
    projected = _unique(official.get("rows"))
    listed = _unique(directory.get("directory_display_observations"))
    originals = _unique(primary.get("observations"))
    if len(fixed) != 20 or set(fixed) != set(projected) or set(fixed) != set(listed):
        raise ValueError("fixed-20 identity mismatch")
    if primary.get("evidence_type") != "fixed20_primary_portal_stage_observations":
        raise ValueError("unsupported primary evidence")
    # Do not promote a caller-supplied portal flag to corroboration without
    # validating the public portal URL, dated display text and matching stage.
    audit(cohort, official, directory, primary)
    first = cohort.get("reviewed_first_record")
    if not isinstance(first, dict) or first.get("publication_number") != "600201-2026":
        raise ValueError("missing independent first-record review")
    # Predeclared, outcome-independent choice among accessible originals;
    # no prevalence or representative-sample claim is supported.
    eligible = sorted(n for n in originals if projected[n]["procedure_main_cpv"].startswith(("48", "72")))
    if tuple(eligible[:3]) != SELECTED:
        raise ValueError("selected IT preflight cohort no longer reproducible")
    cards = []
    incumbent_rows = directory.get("independent_competitor_observations", [])
    if not isinstance(incumbent_rows, list):
        raise ValueError("invalid independent competitor observations")
    for number in SELECTED:
        row = projected[number]
        stage = FIELD_TO_STAGE.get(row.get("field_kind"))
        if stage is None:
            raise ValueError("unknown official stage field")
        main_cpv = row.get("procedure_main_cpv")
        if not isinstance(main_cpv, str) or len(main_cpv) != 8 or not main_cpv.isdigit():
            raise ValueError("invalid main CPV")
        if not main_cpv.startswith(("48", "72")):
            raise ValueError("selected preflight must have primary IT CPV")
        d = listed[number]
        if d.get("source_url") != f"https://upphandla.app/en/tender/{number}":
            raise ValueError("directory URL not bound to notice")
        if d.get("display_status") not in {"date_displayed", "no_deadline_displayed", "page_unavailable"}:
            raise ValueError("unsupported directory status")
        p = originals.get(number)
        if not p or p.get("official_stage") != stage:
            raise ValueError("primary stage mismatch")
        if p.get("official_notice_url") != f"https://ted.europa.eu/sv/notice/{number}/html":
            raise ValueError("unbound primary notice")
        if p.get("amendments_status") != "not_checked":
            raise ValueError("amendment clearance unsupported")
        try:
            date_value = date.fromisoformat(p["official_deadline_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid original date") from exc
        raw = p.get("official_deadline_raw", "")
        if f"{date_value.day:02}/{date_value.month:02}/{date_value.year}" not in raw:
            raise ValueError("original date transcription mismatch")
        original = p["official_notice_url"]
        portal_status = p.get("portal_status")
        if portal_status not in {"public_stage_and_date_text", "not_observed_tool_access"}:
            raise ValueError("unsupported portal status")
        if portal_status == "public_stage_and_date_text" and p.get("portal_stage") != stage:
            raise ValueError("portal stage mismatch")
        matching = [c for c in incumbent_rows if c.get("publication_number") == number]
        if len(matching) > 1:
            raise ValueError("duplicate independent competitor display")
        if matching:
            if matching[0].get("display_status") != "participation_date_displayed":
                raise ValueError("unsupported competitor participation display")
            competitor = [{"source_url": matching[0]["source_url"],
                           "public_display": "participation_date_displayed: " + matching[0]["displayed_date"]}]
        else:
            competitor = ([{"source_url": p["competitor_url"],
                            "public_display": p["competitor_observation"]}]
                          if "competitor_url" in p else [])
        if date_value >= day:
            raise ValueError("historical example date is not yet past")
        for claim in competitor:
            if (not isinstance(claim.get("source_url"), str)
                    or not claim["source_url"].startswith("https://")
                    or not isinstance(claim.get("public_display"), str)
                    or not claim["public_display"].strip()):
                raise ValueError("invalid competitor display evidence")
        cards.append({
            "publication_number": number,
            "original_notice_url": original,
            "official_original_stage": stage,
            "original_notice_deadline_date": date_value.isoformat(),
            "main_cpv": main_cpv,
            "primary_it_cpv_48_or_72": main_cpv.startswith(("48", "72")),
            "directory_url": d["source_url"],
            "directory_display_status": d["display_status"],
            "primary_portal_stage_corroborated": portal_status == "public_stage_and_date_text",
            "competitor_examples_count": len(competitor),
            "competitor_observations": competitor,
            "preflight_action": ACTIONS[number],
            "supplier_bid_no_bid": "UNDETERMINED",
            "historical_not_live_opportunity": True,
            "amendments_and_eligibility_unverified": True,
            "supplier_capability_unknown": True,
        })
    return {
        "evidence_type": "historical_fixed20_source_backed_preflight_examples_not_supplier_decisions",
        "as_of_date": day.isoformat(),
        "example_count": len(cards),
        "examples": cards,
        "actual_paired_supplier_tasks": 0,
        "actual_supplier_time_saved_minutes": None,
        "explicit_price_or_pilot_responses": 0,
        "verified_paying_customers": None,
        "commercial_validation": "NOT_VALIDATED",
        "warning": "Historical notice originals, not amended operative deadlines. No supplier profile, full eligibility review, signed-in portal, incumbent product test, actual bid/no-bid decision, cost, saving or payment evidence."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=Path("data/evidence"))
    parser.add_argument("--as-of", default="2026-10-28")
    args = parser.parse_args()
    files = ("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json",
             "ted_cpv72_search_projection_summary_2026-10-26.json",
             "ted_fixed20_upphandla_stage_visibility_2026-10-26.json",
             "ted_fixed20_primary_portal_stage_2026-10-26.json")
    inputs = [json.loads((args.evidence_dir / name).read_text(encoding="utf-8")) for name in files]
    print(json.dumps(build(*inputs, as_of=args.as_of), indent=2))


if __name__ == "__main__":
    main()
