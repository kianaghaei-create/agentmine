"""Official-only reference projection for the frozen TED-20 evidence.

A partner can compare its own data against this reference without receiving
competitor page content. This is historical Search metadata, not an operative
deadline, a live feed, legal clearance, or a commercial validation result.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from src.ted_lifecycle_chronology import (
    COHORT_PATH, SNAPSHOT_PATH, audit, _publication_id, _uuid, _version,
)

SOURCE_URL = "https://api.ted.europa.eu/v3/notices/search"
LEGAL_URL = "https://ted.europa.eu/en/legal-notice"
API_DOCS = "https://docs.ted.europa.eu/api/latest/search.html"
EVIDENCE_TYPE = "official_TED_search_metadata_frozen20_lifecycle_not_original_or_legal_clearance"


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("missing source timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid source timestamp") from exc
    if result.utcoffset() is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("source timestamp must be UTC")
    return result


def build(snapshot, cohort):
    if (not isinstance(snapshot, dict)
            or snapshot.get("evidence_type") != EVIDENCE_TYPE
            or snapshot.get("source_url") != SOURCE_URL
            or snapshot.get("cohort_path") != COHORT_PATH):
        raise ValueError("official frozen TED source evidence required")
    observed = _utc(snapshot.get("observed_at"))
    life = audit(snapshot, cohort)
    if life["uniform_frozen_deadline_count"] != 20:
        raise ValueError("all frozen notice-level deadlines must resolve")
    source_rows = {_publication_id(r["publication-number"]): r
                   for r in snapshot["rows"]}
    stockholm = ZoneInfo("Europe/Stockholm")
    records = []
    for d in life["deadline_rows"]:
        number = d["publication_number"]
        raw = source_rows[number]
        instant = _utc(d["deadline_utc"])
        # Deliberately construct an allowlisted output. Never forward raw
        # notice dictionaries, contact fields, titles, buyer labels, or
        # third-party display observations from the evidence snapshot.
        records.append({
            "publication_number": number,
            "procedure_identifier": _uuid(raw["procedure-identifier"]),
            "notice_identifier": _uuid(raw["notice-identifier"]),
            "notice_version": _version(raw["notice-version"]),
            "published_stage": d["stage"],
            "published_deadline_utc": d["deadline_utc"],
            "published_deadline_stockholm": instant.astimezone(stockholm).isoformat(),
            "publication_day_start_utc": d["publication_day_start_utc"],
            "publication_day_end_exclusive_utc": d["publication_day_end_exclusive_utc"],
            "official_notice_link": f"https://ted.europa.eu/en/notice/{number}/html",
            "deadline_scope": "uniform_notice_level_search_metadata",
            "operative_deadline_verified": False,
        })
    changes = []
    for c in life["change_rows"]:
        # Unresolved references are retained, not promoted to changes.
        item = {"change_publication_number": c["change_publication_number"],
                "prior_publication_number": c["prior_publication_number"],
                "status": c["status"]}
        if c["status"] == "linked_uniform_same_stage_metadata":
            for key in ("stage", "prior_deadline_utc", "new_deadline_utc",
                        "deadline_change_seconds"):
                item[key] = c[key]
        changes.append(item)
    return {
        "evidence_type": "historical_official_only_TED_reference_not_legal_or_customer_outcome",
        "source": {
            "publisher": "Publications Office of the European Union",
            "attribution": "Source: TED, Supplement to the Official Journal of the European Union.",
            "source_url": SOURCE_URL,
            "source_observed_at_utc": observed.astimezone(timezone.utc).isoformat(),
            "source_snapshot": SNAPSHOT_PATH,
            "cohort_path": COHORT_PATH,
            "reuse_policy_url": LEGAL_URL,
            "api_documentation_url": API_DOCS,
            "reuse_scope": "Published procurement notices may be reused commercially or noncommercially unless otherwise noted; third-party rights and personal data may require separate clearance.",
            "transformation": "Selected official notice identifiers and uniform deadline projections; normalized UTC and Europe/Stockholm instants; linked change metadata. No third-party page content or raw contact fields.",
            "rights_limit": "Publisher policy is not record-specific legal clearance, permission to redistribute third-party portal content, or authorization to process personal data.",
        },
        "fixed_notice_count": len(records),
        "related_publication_count": life["lifecycle_notice_count"],
        "records": records,
        "linked_change_metadata": changes,
        "new_source_requests": 0,
        "third_party_observations_in_output": 0,
        "operative_deadline_verification_count": 0,
        "amendment_histories_cleared": 0,
        "verified_supplier_outcomes": None,
        "verified_agentmine_revenue": None,
        "warning": "Historical, selected official Search metadata only. Notice links are references, not new document inspections. Publication day is an interval, not an exact publication timestamp. Not live alerts, legal cutoffs, complete amendment histories, market prevalence, supplier savings, willingness to pay or a deployed service.",
    }


def from_root(root=Path(".")):
    return build(json.loads((root / SNAPSHOT_PATH).read_text(encoding="utf-8")),
                 json.loads((root / COHORT_PATH).read_text(encoding="utf-8")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    rendered = json.dumps(from_root(args.root), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
