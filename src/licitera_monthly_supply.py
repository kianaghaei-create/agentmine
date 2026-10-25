"""Offline, license-attributed analysis of Licitera's free monthly CSV exports.

This does not fetch, authenticate, pay or use restricted historical exports.
Counts are *publisher-supplied monthly file cohorts*, not all Swedish tenders,
verified unique companies, live RFQs, paying customers or AgentMine revenue.

Source and license: https://licitera.se/oppen-data (CC BY 4.0 monthly files).
Attribution: Licitera (licitera.se), CC BY 4.0; compiled from TED,
Upphandlingsmyndigheten and Konkurrensverket. UHM data processed by Licitera.
"""
import argparse
from collections import Counter
import csv
from datetime import date
import gzip
import io
import json
from pathlib import Path
import re

_MONTH = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
_CPV = re.compile(r"^[0-9]{8}(?:-[0-9])?$")
_ISO_DAY = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$")
_REQUIRED_PROC = {"Internt id", "Köpare-id", "Huvud-CPV", "Publicerad", "Källreferens"}
_REQUIRED_AWARD = {"Internt id", "Upphandling-id", "Leverantör-id"}
_MAX_BYTES = 12_000_000
_MAX_ROWS = 100_000


def _rows(path, required):
    """Read the documented UTF-8 BOM / semicolon / # metadata format.

    Bound decompressed bytes so an untrusted gzip file cannot exhaust memory.
    """
    path = Path(path)
    with (gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")) as handle:
        data = handle.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("monthly export exceeds offline size cap")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("monthly export must be UTF-8") from exc
    lines = decoded.splitlines(keepends=True)
    # Publisher metadata may contain blank lines or indented comment markers.
    # Strip only the leading preamble, never comments inside CSV records.
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
        lines.pop(0)
    content = "".join(lines)
    reader = csv.DictReader(io.StringIO(content), delimiter=";", strict=True)
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("monthly export missing required documented columns")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("duplicate CSV header")
    rows = []
    try:
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("malformed CSV row")
            if len(rows) >= _MAX_ROWS:
                raise ValueError("monthly export exceeds row cap")
            rows.append(row)
    except csv.Error as exc:
        raise ValueError("malformed CSV") from exc
    return rows


def _id(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError(f"invalid {field}")
    return value.strip()


def _concentration(counts):
    n = sum(counts.values())
    return {"known_id_rows": n, "distinct_unverified_ids": len(counts),
            "top_id_row_share": max(counts.values()) / n if n else None,
            "id_hhi_in_known_monthly_file": sum((v / n) ** 2 for v in counts.values()) if n else None}


def analyze(procurement_csv, *, expected_month, award_csv=None):
    """Separate September-style tender-publication and award-file cohorts.

    The two exports are not assumed to have identical publication cohorts.
    Supplier concentration refers to *award rows*, not buyer payments or the
    share of tender notices. No names, IDs, contract values or raw rows leave.
    """
    if not isinstance(expected_month, str) or not _MONTH.fullmatch(expected_month):
        raise ValueError("expected_month must be YYYY-MM")
    procurements = _rows(procurement_csv, _REQUIRED_PROC)
    seen, buyers, main_cpv, statuses, sources = set(), Counter(), Counter(), Counter(), Counter()
    unknown_buyer = unknown_cpv = missing_reference = 0
    for row in procurements:
        identifier = _id(row["Internt id"], "procurement ID")
        if identifier in seen:
            raise ValueError("duplicate procurement ID in monthly export")
        seen.add(identifier)
        if not _ISO_DAY.fullmatch(row["Publicerad"]):
            raise ValueError("invalid publication date")
        try:
            published = date.fromisoformat(row["Publicerad"])
        except ValueError as exc:
            raise ValueError("invalid publication date") from exc
        if published.strftime("%Y-%m") != expected_month:
            raise ValueError("procurement outside expected publication month")
        buyer = row["Köpare-id"].strip()
        if buyer:
            buyers[_id(buyer, "buyer ID")] += 1
        else:
            unknown_buyer += 1
        cpv = row["Huvud-CPV"].strip()
        if not cpv:
            unknown_cpv += 1
        elif not _CPV.fullmatch(cpv):
            raise ValueError("invalid main CPV code")
        else:
            main_cpv[cpv[:2]] += 1
        status = row.get("Status", "").strip().lower()
        source = row.get("Källa", "").strip().lower()
        statuses[status if status in {"open", "awarded", "cancelled", "closed"} else "unknown_or_other"] += 1
        sources[source if source in {"ted", "uhm"} else "unknown_or_other"] += 1
        if not row["Källreferens"].strip():
            missing_reference += 1
    result = {
        "evidence_type": "publisher_monthly_public_procurement_supply_not_agent_demand",
        "publisher": "Licitera", "publisher_source_url": "https://licitera.se/oppen-data",
        "license": "CC BY 4.0 (monthly public exports only)",
        "attribution": "Licitera (licitera.se), CC BY 4.0; Uppgifter: Upphandlingsmyndigheten | Bearbetning: Licitera | Analys: AgentMine",
        "publication_month": expected_month,
        "procurement_rows": len(procurements),
        "main_cpv48_rows": main_cpv["48"], "main_cpv72_rows": main_cpv["72"],
        "other_known_main_cpv_rows": sum(main_cpv.values()) - main_cpv["48"] - main_cpv["72"],
        "unknown_main_cpv_rows": unknown_cpv,
        "missing_source_reference_rows": missing_reference,
        "unknown_buyer_id_rows": unknown_buyer,
        "buyer_id_concentration": _concentration(buyers),
        "status_row_counts": dict(sorted(statuses.items())),
        "source_row_counts": dict(sorted(sources.items())),
        "award_file": None,
        "verified_supplier_businesses": None,
        "verified_agentmine_buyers": None,
        "verified_paying_customers": None,
        "agentmine_revenue_sek": None,
        "warning": "One publisher's monthly publication cohort, not a national census. "
                   "CPV48 and CPV72 count MAIN codes only. IDs are publisher labels, not verified businesses. "
                   "Status is publisher-reported, not independent outcome validation. "
                   "Missing outcomes and cross-month awards prohibit bid-intensity or conversion claims.",
    }
    if award_csv is not None:
        awards = _rows(award_csv, _REQUIRED_AWARD)
        award_ids, suppliers = set(), Counter()
        unknown_supplier = matched = 0
        for row in awards:
            aid = _id(row["Internt id"], "award ID")
            if aid in award_ids:
                raise ValueError("duplicate award ID in monthly export")
            award_ids.add(aid)
            procurement_id = _id(row["Upphandling-id"], "award procurement ID")
            matched += int(procurement_id in seen)
            supplier_id = row["Leverantör-id"].strip()
            if supplier_id:
                suppliers[_id(supplier_id, "supplier ID")] += 1
            else:
                unknown_supplier += 1
        result["award_file"] = {
            "award_rows": len(awards),
            "award_rows_joined_to_same_month_procurements": matched,
            "award_rows_not_joined_to_same_month_procurements": len(awards) - matched,
            "unknown_supplier_id_rows": unknown_supplier,
            "supplier_id_concentration": _concentration(suppliers),
            "warning": "Award rows and published tenders are DIFFERENT monthly cohorts. "
                       "Unmatched awards are expected; do not divide awards by tender rows to infer conversion. "
                       "Supplier IDs are unverified publisher labels, not distinct paying firms.",
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procurements", type=Path, required=True)
    parser.add_argument("--awards", type=Path)
    parser.add_argument("--month", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.procurements, expected_month=args.month,
                             award_csv=args.awards), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
