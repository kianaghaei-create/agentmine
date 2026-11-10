"""Offline source-quality feed for the frozen TED-20 cohort.

Compose the existing validated source audits; do not scrape, infer a legal
deadline, or count a review item as a customer outcome. The historical
observations are not synchronized and must never be sent as live alerts.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from src.ted_lifecycle_chronology import audit as lifecycle_audit, SNAPSHOT_PATH, COHORT_PATH
from src.ted_initask_stage_visibility import audit as initask_audit, EVIDENCE_PATH as INITASK_PATH
from src.tender_stage_incumbent_audit import audit as upphandla_audit
from src.tender_deadline_display_audit import audit as original_audit
from src.ted_linked_deadline_display import audit as linked_audit, CHRONOLOGY, EVIDENCE as LINKED_PATH

UPPHANDLA_PATH = "data/evidence/ted_fixed20_upphandla_stage_visibility_2026-10-26.json"
PROJECTION_PATH = "data/evidence/ted_cpv72_search_projection_summary_2026-10-26.json"
ORIGINAL_PATH = "data/evidence/ted_fixed20_all_displayed_date_hypothesis_2026-11-10.json"
INPUT_PATHS = (COHORT_PATH, SNAPSHOT_PATH, PROJECTION_PATH, UPPHANDLA_PATH,
               INITASK_PATH, ORIGINAL_PATH, CHRONOLOGY, LINKED_PATH)


def _instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("offset required")
    return result.astimezone(timezone.utc)


def build(cohort, snapshot, projection, upphandla, initask, originals,
          chronology, linked):
    life = lifecycle_audit(snapshot, cohort)
    if life["uniform_frozen_deadline_count"] != 20:
        raise ValueError("all frozen source deadlines must resolve")
    ua = upphandla_audit(cohort, projection, upphandla)
    ia = initask_audit(snapshot, cohort, initask)
    oa = original_audit(originals, cohort)
    la = linked_audit(chronology, linked)
    if chronology["source_observed_at"] != snapshot["observed_at"]:
        raise ValueError("chronology snapshot timestamp mismatch")
    # Bind the selected change to the actual recomputed lifecycle, not merely
    # to a separately supplied chronology summary.
    changes = [x for x in life["change_rows"]
               if x["status"] == "linked_uniform_same_stage_metadata"]
    if len(changes) != 1:
        raise ValueError("expected one resolved linked change")
    change = changes[0]
    for key in ("prior_publication_number", "change_publication_number",
                "prior_deadline_utc", "new_deadline_utc", "deadline_change_seconds"):
        if change[key] != chronology["change"][key]:
            raise ValueError("linked chronology does not match source metadata")
    official = {x["publication-number"]: x for x in snapshot["rows"]}
    prior_projection = {x["publication_number"]: x for x in projection["rows"]}
    u = {x["publication_number"]: x for x in ua["items"]}
    i = {x["publication_number"]: x for x in ia["items"]}
    orig = {x["publication_number"]: x for x in originals["attempts"]
            if x["status"] == "observed"}
    displayed = {n for n, x in u.items()
                 if x["directory_display_status"] == "date_displayed"}
    if set(orig) != displayed or oa["compared"] != len(displayed):
        raise ValueError("original audit must cover every Upphandla displayed date")
    if originals.get("cohort_path") != COHORT_PATH:
        raise ValueError("original audit cohort mismatch")
    comparator = {x["publication_number"]: x
                  for x in upphandla["independent_competitor_observations"]}
    pages = {x["provider"]: x for x in linked["pages"]}
    records = []
    stockholm = ZoneInfo("Europe/Stockholm")
    for row in life["deadline_rows"]:
        n, stage = row["publication_number"], row["stage"]
        source = official[n]
        old = prior_projection[n]
        ur, ir = u[n], i[n]
        if (old["procedure_identifier"] != source["procedure-identifier"]
                or ur["official_published_field_stage"] !=
                ("participation_request" if stage == "participation" else stage)
                or ir["source_stage"] != stage):
            raise ValueError("cross-snapshot procedure or stage mismatch")
        utc = _instant(row["deadline_utc"])
        local = utc.astimezone(stockholm)
        utc_day, local_day = utc.date().isoformat(), local.date().isoformat()
        u_date = ur["directory_displayed_date"]
        i_minute = ir["displayed_minute"]
        u_status = ur["directory_display_status"]
        i_status = ir["classification"]
        flags, context = [], []
        if u_status == "no_deadline_displayed":
            flags.append("upphandla_published_stage_deadline_not_visible")
        if i_status == "published_stage_deadline_not_visible":
            flags.append("initask_published_stage_deadline_not_visible")
        if ir.get("utc_clock_only_match"):
            flags.append("initask_utc_only_offsetless_clock")
        if i_minute is not None and (not ir.get("stage_matches") or
                                     not ir.get("source_clock_matches")):
            flags.append("initask_stage_or_source_clock_difference")
        original_url = None
        u_relation = "not_comparable"
        if u_date is not None:
            original = orig[n]
            if (_instant(original["official_original_datetime"]) != utc
                    or original["directory_display_date"] != u_date):
                raise ValueError("original instant or directory date does not match joined evidence")
            original_url = original["official_notice_url"]
            if u_date not in (utc_day, local_day):
                u_relation = "neither_utc_nor_stockholm_date"
                flags.append("upphandla_date_not_utc_or_stockholm")
            elif u_date == utc_day and utc_day != local_day:
                u_relation = "utc_date_only_compatible"
                context.append("date_only_timezone_ambiguity")
            else:
                u_relation = "stockholm_date_compatible"
        cross_date = "not_comparable"
        if u_date is not None and i_minute is not None:
            if i_minute[:10] == u_date:
                cross_date = "same_calendar_label"
            elif (u_relation == "utc_date_only_compatible"
                  and i_minute[:10] == local_day):
                cross_date = "different_utc_stockholm_compatible"
            elif (u_relation == "neither_utc_nor_stockholm_date"
                  and ir.get("source_clock_matches") and ir.get("stage_matches")):
                cross_date = "different_upphandla_neither_utc_nor_stockholm"
            else:
                cross_date = "different_other_or_unresolved"
        comparison = None
        if n in comparator:
            c = comparator[n]
            comparison = {"source_url": c["source_url"],
                          "observed_at": upphandla["observed_at_utc"],
                          "display_status": c["display_status"],
                          "displayed_date": c.get("displayed_date"),
                          "explicit_participation_date_matches_stockholm": (
                              stage == "participation" and
                              c["display_status"] == "participation_date_displayed" and
                              c.get("displayed_date") == local_day)}
        linked_context = None
        if n == change["change_publication_number"]:
            if source["procedure-identifier"] != linked["procedure_identifier"]:
                raise ValueError("selected linked procedure mismatch")
            linked_context = {"prior_notice_id": change["prior_publication_number"],
                              "new_notice_id": n,
                              "prior_deadline_utc": change["prior_deadline_utc"],
                              "new_deadline_utc": change["new_deadline_utc"],
                              "retrieved_on": linked["retrieved_on"],
                              "procedure_pages": []}
            for p in la["rows"]:
                if p["scope"] != "procedure":
                    continue
                linked_context["procedure_pages"].append({
                    "provider": p["provider"], "source_url": pages[p["provider"]]["url"],
                    "headline_date": p["headline_date"],
                    "latest_notice_date_matches": p["headline_matches_comparison_notice"],
                    "prior_headline_latest_detail_conflict":
                        p["same_page_prior_headline_latest_detail_conflict"]})
                if p["same_page_prior_headline_latest_detail_conflict"]:
                    flags.append("linked_procedure_headline_history_conflict")
        records.append({
            "publication_number": n, "procedure_identifier": source["procedure-identifier"],
            "official_stage": stage, "official_deadline_utc": row["deadline_utc"],
            "official_stockholm_date": local_day, "official_utc_date": utc_day,
            "official_metadata_observed_at": snapshot["observed_at"],
            "official_metadata_source_url": snapshot["source_url"],
            "previously_inspected_original_url": original_url,
            "upphandla": {"source_url": ur["directory_source_url"],
                          "observed_at": upphandla["observed_at_utc"],
                          "status": u_status, "displayed_date": u_date,
                          "date_relation": u_relation},
            "initask": {"source_url": ir["source_url"], "observed_on": initask["observed_on"],
                        "status": i_status, "displayed_minute": i_minute,
                        "visible_offset": None},
            "cross_provider_date_relation": cross_date,
            "tilldelat_selected_comparator": comparison,
            "linked_change_selected_comparison": linked_context,
            "review_codes": sorted(set(flags)), "context_codes": sorted(set(context)),
            "historical_review_required": bool(flags),
            "operative_deadline_verified": False,
        })
    counts = Counter(x["cross_provider_date_relation"] for x in records)
    both_missing = [x for x in records if
                    x["upphandla"]["status"] == "no_deadline_displayed" and
                    x["initask"]["status"] == "published_stage_deadline_not_visible"]
    both_rendered = sum(x["upphandla"]["status"] != "page_unavailable" and
                        x["initask"]["status"] != "unavailable_unknown" for x in records)
    counterexamples = [x for x in records if x["tilldelat_selected_comparator"] and
                       x["tilldelat_selected_comparator"]["explicit_participation_date_matches_stockholm"]]
    return {
        "evidence_type": "historical_fixed20_source_quality_review_feed",
        "input_paths": list(INPUT_PATHS),
        "official_metadata_observed_at": snapshot["observed_at"],
        "fixed_notice_count": len(records),
        "both_directories_rendered_count": both_rendered,
        "both_directories_omit_deadline_count": len(both_missing),
        "both_omit_notice_ids": sorted(x["publication_number"] for x in both_missing),
        "paired_date_labels_count": len(records) - counts["not_comparable"],
        "paired_date_relation_counts": dict(sorted(counts.items())),
        "previously_inspected_original_instants_reconciled": len(orig),
        "selected_tilldelat_participation_date_matches": len(counterexamples),
        "selected_tilldelat_matches_where_both_omit": sum(x in both_missing for x in counterexamples),
        "historical_review_notice_count": sum(x["historical_review_required"] for x in records),
        "review_code_counts": dict(sorted(Counter(
            c for x in records for c in x["review_codes"]).items())),
        "records": records,
        "new_original_or_portal_inspections": 0,
        "verified_legal_deadline_errors": None,
        "verified_supplier_outcomes": None,
        "verified_agentmine_revenue": None,
        "warning": "Historical non-synchronized rendered/cached observations, not live alerts, "
                   "market prevalence, legal cutoff, supplier harm, savings or willingness to pay. "
                   "Date-only UTC/Stockholm compatibility is not a verified instant. "
                   "Unavailable pages are unknown; selected comparator pages are not a full cohort."
    }


def from_root(root=Path(".")):
    return build(*(json.loads((root / p).read_text(encoding="utf-8")) for p in INPUT_PATHS))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = json.dumps(from_root(args.root), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
