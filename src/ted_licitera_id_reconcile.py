"""Aggregate-only TED/Licitera CPV7231 notice-ID reconciliation.

Compares the official TED September 2026 Sweden publication-number cohort with
Licitera's free CC BY 4.0 previous-month procurement export. No raw IDs, names,
notices or customer information in output. Matching is strict, not fuzzy.
Not an incumbent product recall test or a live deadline check.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from src.licitera_monthly_supply import _rows, _publication_date
from src.licitera_cpv_segment import _cpvs
from src.licitera_public_monthly_runner import fetch_public_file
from src.ted_notice_evidence import collect, post_json
from src.ted_cpv7231_public_probe import QUERY, SOURCE, EXPECTED_MONTH, summarize
from src.ted_title_gap_triage import triage as triage_unmatched_titles
from src.ted_procedure_gap_triage import triage as triage_unmatched_procedures
from src.ted_cross_month_procedure import CROSS_MONTH_QUERY, triage_cross_month
from src.ted_target_procedure_probe import probe as probe_unlinked_procedure

TED_RECONCILIATION_FIELDS = ["publication-number", "publication-date", "notice-type", "notice-title",
                             "buyer-name", "buyer-country", "classification-cpv",
                             "procedure-identifier", "previous-notice-id-proc"]

_PUBLICATION_NUMBER = re.compile(r"^[0-9]{6}-20[0-9]{2}$")
_TED_PATH = re.compile(r"^/(?:[a-z]{2}/)?notice/-/detail/([0-9]{6}-20[0-9]{2})/?$")
_REQUIRED = {"Internt id", "Publicerad", "Huvud-CPV", "CPV-koder", "Källa", "Källreferens"}


def reference_number(reference):
    """Only exact publication numbers or canonical ted.europa.eu detail URLs.

    Other forms are *unknown*, not silently converted to a different ID.
    """
    if not isinstance(reference, str):
        return None
    ref = reference.strip()
    if _PUBLICATION_NUMBER.fullmatch(ref):
        return ref
    try:
        url = urlsplit(ref)
    except ValueError:
        return None
    try:
        valid_host = (url.scheme == "https" and url.hostname == "ted.europa.eu"
                      and url.port in (None, 443))
    except ValueError:
        return None
    if not valid_host:
        return None
    if url.username or url.password or url.query or url.fragment:
        return None
    m = _TED_PATH.fullmatch(url.path)
    return m.group(1) if m else None


def reconcile(rows, ted_snapshot, cross_month_snapshot=None, *, cross_cpv_fetcher=None):
    """Return only cohort aggregates. Inputs must remain ephemeral and private to runner.

    Denominators: Licitera procurement rows versus TED *publication numbers*;
    even an exact match does not imply the two publishers cover equal cohorts.
    """
    ted_summary = summarize(ted_snapshot)
    if not ted_summary["complete_for_query"]:
        raise ValueError("TED cohort incomplete; cannot calculate ID coverage")
    if (ted_summary["buyer_country_filter_mismatch_rows"]
            or ted_summary["missing_buyer_country_rows"]
            or ted_summary["no_7231_cpv_in_returned_fields_rows"]
            or ted_summary["missing_classification_cpv_rows"]):
        raise ValueError("TED query projection inconsistent; fail closed")
    if not isinstance(rows, list):
        raise ValueError("invalid Licitera rows")
    ted_ids = {r["publication-number"]: r for r in ted_snapshot["notices"]}
    seen_internal = set()
    ted_ref_ids = set()
    matched_ids = set()
    all_licitera_matched_ted_ids = set()
    source_labels = Counter()
    ref_types = Counter()
    matched_types = Counter()
    matched_main_union = Counter()
    matched_status = Counter()
    licitera_rows = selected = 0
    for row in rows:
        if not isinstance(row, dict) or not _REQUIRED.issubset(row):
            raise ValueError("invalid Licitera row schema")
        ident = row["Internt id"].strip()
        if not ident or ident in seen_internal:
            raise ValueError("missing or duplicate Licitera internal ID")
        seen_internal.add(ident)
        licitera_rows += 1
        _publication_date(row["Publicerad"].strip(), EXPECTED_MONTH)
        main = row["Huvud-CPV"].strip()
        codes = _cpvs(row["CPV-koder"])
        if main:
            if not re.fullmatch(r"[0-9]{8}(?:-[0-9])?", main):
                raise ValueError("invalid main CPV")
            codes.add(main)
        source = row["Källa"].strip().lower()
        # Search the WHOLE monthly export before filtering to Licitera's
        # 7231 rows. A TED notice absent from that cohort may still exist
        # under a different Licitera CPV classification.
        if source == "ted":
            any_ref = reference_number(row["Källreferens"].strip())
            if any_ref in ted_ids:
                all_licitera_matched_ted_ids.add(any_ref)
        if not any(code.startswith("7231") for code in codes):
            continue
        selected += 1
        source_labels[source if source == "ted" else "other_or_unknown"] += 1
        if source != "ted":
            continue
        ref = row["Källreferens"].strip()
        if not ref:
            ref_types["missing"] += 1
            continue
        pub = reference_number(ref)
        if pub is None:
            ref_types["unsupported_format"] += 1
            continue
        ref_types["recognized"] += 1
        ted_ref_ids.add(pub)
        if pub not in ted_ids:
            continue
        matched_ids.add(pub)
        notice_type = ted_ids[pub].get("notice-type", "")
        kind = "contract_notice" if isinstance(notice_type, str) and notice_type.startswith("cn-") else (
            "award_notice" if isinstance(notice_type, str) and notice_type.startswith("can-") else "other")
        matched_types[kind] += 1
        matched_main_union["covered" if main[:2] in {"48", "72"} else "missed"] += 1
        status = row.get("Status", "").strip().lower()
        matched_status[status if status in {"open", "awarded", "closed", "cancelled"} else "other_or_unknown"] += 1
    recognized = ref_types["recognized"]
    matched_rows = sum(matched_types.values())
    if matched_rows > recognized or len(matched_ids) > len(ted_ids):
        raise ValueError("impossible join counts")
    unmatched_ted_types = Counter()
    unmatched_found_elsewhere = Counter()
    unmatched_absent_from_export = Counter()
    unmatched_contract_absent = []
    for pub, notice in ted_ids.items():
        if pub in matched_ids:
            continue
        kind = notice.get("notice-type")
        if isinstance(kind, str) and kind.startswith("cn-"):
            unmatched_ted_types["contract_notice"] += 1
        elif isinstance(kind, str) and kind.startswith("can-"):
            unmatched_ted_types["contract_award_notice"] += 1
        else:
            unmatched_ted_types["other_or_unknown"] += 1
        kind = ("contract_notice" if isinstance(kind, str) and kind.startswith("cn-") else
                "contract_award_notice" if isinstance(kind, str) and kind.startswith("can-") else
                "other_or_unknown")
        if pub in all_licitera_matched_ted_ids:
            unmatched_found_elsewhere[kind] += 1
        else:
            unmatched_absent_from_export[kind] += 1
            if kind == "contract_notice":
                unmatched_contract_absent.append(notice)
    if (sum(unmatched_found_elsewhere.values()) + sum(unmatched_absent_from_export.values())
            != len(ted_ids) - len(matched_ids)):
        raise ValueError("TED unmatched cohort decomposition failed")
    title_triage = triage_unmatched_titles(rows, unmatched_contract_absent, month=EXPECTED_MONTH)
    procedure_triage = triage_unmatched_procedures(list(ted_ids.values()), matched_ids,
                                                   unmatched_contract_absent)
    if title_triage["unmatched_ted_contract_notices"] != unmatched_absent_from_export["contract_notice"]:
        raise ValueError("unmatched contract title triage does not reconcile")
    cross_month_triage = (triage_cross_month(list(ted_ids.values()), matched_ids,
                           unmatched_contract_absent, cross_month_snapshot)
                          if cross_month_snapshot is not None else None)
    if cross_cpv_fetcher is not None and cross_month_snapshot is None:
        raise ValueError("cross-CPV probe requires validated cross-month cohort")
    target_probe = (probe_unlinked_procedure(list(ted_ids.values()), matched_ids,
                    unmatched_contract_absent, cross_month_snapshot,
                    fetch_page=cross_cpv_fetcher, fields=TED_RECONCILIATION_FIELDS)
                    if cross_cpv_fetcher is not None else None)
    return {
        "evidence_type": "exact_publication_number_cross_source_cohort_join_not_competitor_recall",
        "publication_month": EXPECTED_MONTH,
        "ted_query": QUERY,
        "ted_source": SOURCE,
        "licitera_source": "https://licitera.se/oppen-data",
        "licitera_attribution": "Licitera (licitera.se), CC BY 4.0; Uppgifter: Upphandlingsmyndigheten | Bearbetning: Licitera | Analys: AgentMine",
        "ted_complete_for_query": True,
        "ted_publication_numbers": len(ted_ids),
        "licitera_total_procurement_rows": licitera_rows,
        "licitera_any_cpv7231_procurement_rows": selected,
        "licitera_7231_source_labels": dict(sorted(source_labels.items())),
        "licitera_ted_reference_formats": dict(sorted(ref_types.items())),
        "licitera_distinct_recognized_ted_references": len(ted_ref_ids),
        "exact_joined_licitera_rows": matched_rows,
        "exact_joined_distinct_ted_publication_numbers": len(matched_ids),
        "matched_ted_notice_types": dict(sorted(matched_types.items())),
        "matched_licitera_broad_main_48_72_baseline": dict(sorted(matched_main_union.items())),
        "matched_licitera_publisher_status_not_live": dict(sorted(matched_status.items())),
        "ted_publication_numbers_without_exact_licitera_join": len(ted_ids) - len(matched_ids),
        "ted_unmatched_notice_types": dict(sorted(unmatched_ted_types.items())),
        "ted_unmatched_7231_notice_types_found_in_other_licitera_rows": dict(sorted(unmatched_found_elsewhere.items())),
        "ted_unmatched_notice_types_absent_from_entire_licitera_export": dict(sorted(unmatched_absent_from_export.items())),
        "ted_publication_numbers_matched_anywhere_in_licitera_export": len(all_licitera_matched_ted_ids),
        "ted_contract_absent_from_export_title_date_triage": title_triage,
        "ted_contract_absent_from_export_official_procedure_triage": procedure_triage,
        "ted_contract_absent_cross_month_official_procedure_triage": cross_month_triage,
        "ted_contract_absent_all_cpv_official_procedure_probe": target_probe,
        "cross_source_recall_estimate": None,
        "verified_incumbent_search_misses": None,
        "verified_current_open_deadlines": None,
        "verified_supplier_time_savings": None,
        "verified_agentmine_paying_customers": None,
        "verified_agentmine_revenue": None,
        "warning": "TED notices include contract and award types; Licitera rows are procurement entities. Unmatched 7231-cohort IDs are separately checked against all Licitera rows; absence from the export is not proof of missing product coverage, due to timing, scope or entity granularity. Publisher open status is not a current deadline. Source IDs and titles are never emitted. Title/date candidates do not prove identity. Exact joins do not establish competitor recall, supplier fit, time savings or payment demand."
    }


def run(*, fetcher=fetch_public_file, ted_fetcher=None, now=None, cross_month=False, cross_cpv=False):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    if cross_cpv and not cross_month:
        raise ValueError("cross-CPV requires cross-month cohort")
    if now.strftime("%Y-%m") != "2026-10":
        raise ValueError("September 2026 is no longer the previous-month free cohort")
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "upphandlingar.csv.gz"
        source = fetcher("upphandlingar.csv.gz", path)
        snapshot = collect(QUERY, max_pages=2, limit=100, fields=TED_RECONCILIATION_FIELDS,
                           **({"fetch_page": ted_fetcher} if ted_fetcher else {}))
        extended = (collect(CROSS_MONTH_QUERY, max_pages=3, limit=100,
                            fields=TED_RECONCILIATION_FIELDS,
                            **({"fetch_page": ted_fetcher} if ted_fetcher else {}))
                    if cross_month else None)
        result = reconcile(_rows(path, _REQUIRED), snapshot, extended,
                           cross_cpv_fetcher=(ted_fetcher or post_json) if cross_cpv else None)
        if extended is not None:
            result["ted_cross_month_observed_at"] = extended["observed_at"]
        result["observed_at_utc"] = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        result["licitera_source_file"] = source
        result["ted_observed_at"] = snapshot["observed_at"]
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cross-month", action="store_true",
                   help="Run bounded official Aug-Oct 2026 TED procedure identity check")
    p.add_argument("--cross-cpv", action="store_true",
                   help="Check unresolved TED procedure UUID across all CPVs (bounded 2026)")
    args = p.parse_args()
    report = run(cross_month=args.cross_month, cross_cpv=args.cross_cpv)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Cross-source CPV7231 exact ID reconciliation:",
          json.dumps({k: report[k] for k in (
              "ted_publication_numbers", "licitera_any_cpv7231_procurement_rows",
              "licitera_ted_reference_formats", "exact_joined_licitera_rows",
              "exact_joined_distinct_ted_publication_numbers",
              "ted_unmatched_7231_notice_types_found_in_other_licitera_rows",
              "ted_unmatched_notice_types_absent_from_entire_licitera_export")}, ensure_ascii=False))
    cross = report.get("ted_contract_absent_cross_month_official_procedure_triage")
    if cross is not None:
        print("Official bounded TED cross-month procedure identity:",
              json.dumps({k: cross[k] for k in (
                  "extended_publication_numbers", "publication_month_counts",
                  "unmatched_contract_notices", "procedure_link_categories")},
                         ensure_ascii=False))
    targeted = report.get("ted_contract_absent_all_cpv_official_procedure_probe")
    if targeted is not None:
        print("Official targeted TED all-CPV procedure identity:",
              json.dumps({k: targeted[k] for k in (
                  "notices_in_procedure", "peer_notices", "peer_publication_months",
                  "peer_cpv_categories", "peer_notice_types")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
