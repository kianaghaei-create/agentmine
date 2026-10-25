"""Fetch only Licitera's openly licensed previous-month bulk files and emit aggregates.

No login, pagination, restricted history, buyer identities, external payments or
public deployment. Raw files remain in a temporary directory and are deleted.
Source: https://licitera.se/oppen-data (CC BY 4.0, attribution required).
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen

from src.licitera_cpv_segment import analyze as analyze_segments
from src.licitera_cpv_subfamily import analyze as analyze_subfamilies
from src.licitera_award_cpv_cohort import analyze as analyze_award_cpv
from src.licitera_monthly_supply import analyze as analyze_supply

_BASE = "https://licitera.se/oppen-data/"
_NAMES = ("upphandlingar.csv.gz", "tilldelningar.csv.gz")
_MAX_COMPRESSED = 2_000_000



def public_header_diagnostic(path):
    """Report only public CSV column labels, never the first data record."""
    known = {"Internt id", "Köpare-id", "Huvud-CPV", "CPV-koder",
             "Publicerad", "Källreferens", "Källa", "Upphandling-id",
             "Leverantör-id", "Titel", "Status"}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if line_number > 16:
                break
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            columns = next(csv.reader([line], delimiter=";"))
            recognized = "Internt id" in columns and len(columns) >= 3
            safe = (sum(value in known for value in columns) >= 2
                    and all(0 < len(value) <= 80 and "@" not in value
                            and "\\n" not in value for value in columns))
            return {"candidate_line": line_number, "column_count": len(columns),
                    "recognized_header": recognized,
                    "column_names": columns if safe else None}
    return {"candidate_line": None, "column_count": 0,
            "recognized_header": False, "column_names": None}



def public_date_diagnostic(path):
    """Aggregate public date-field shapes without logging tender rows or IDs."""
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        lines = handle.readlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
        lines.pop(0)
    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter=";")
    shapes = Counter()
    safe_examples = []
    anonymized_shapes = Counter()
    for row in reader:
        value = (row.get("Publicerad") or "").strip()
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
            shapes["iso_date"] += 1
        elif not value:
            shapes["missing"] += 1
        elif re.fullmatch(r"20\d{2}-\d{2}-\d{2}[T ][0-9:.+Z-]{2,35}", value):
            shapes["iso_datetime"] += 1
        else:
            shapes["other"] += 1
            masked = "".join("9" if char.isdigit() else "A" if char.isalpha() else char for char in value[:60])
            anonymized_shapes[masked] += 1
        if shapes["other"] and len(safe_examples) < 3 and (re.fullmatch(r"[0-9TZ:+. /-]{1,40}", value) or re.fullmatch(r"[A-Za-zÅÄÖåäö]{3} [A-Za-zÅÄÖåäö]{3} [0-9]{2}", value)):
            if value not in safe_examples:
                safe_examples.append(value)
    return {"date_shapes": dict(shapes), "safe_other_examples": safe_examples,
            "anonymized_other_patterns": anonymized_shapes.most_common(4)}


def previous_month(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    year, month = now.year, now.month
    return f"{year - 1 if month == 1 else year:04d}-{12 if month == 1 else month - 1:02d}"


def fetch_public_file(name, destination, *, opener=urlopen):
    if name not in _NAMES:
        raise ValueError("only public monthly procurement and award files are permitted")
    req = Request(_BASE + name, headers={"User-Agent": "AgentMine-public-monthly-research/1.0", "Accept": "application/gzip"})
    with opener(req, timeout=20) as response:
        if response.status != 200:
            raise ValueError("unexpected download HTTP status")
        mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if mime not in {"application/gzip", "application/x-gzip", "application/octet-stream"}:
            raise ValueError("unexpected download content type")
        claimed = response.headers.get("Content-Length")
        if claimed is not None and (not claimed.isdecimal() or int(claimed) > _MAX_COMPRESSED):
            raise ValueError("download length invalid or exceeds cap")
        payload = response.read(_MAX_COMPRESSED + 1)
    if len(payload) > _MAX_COMPRESSED or not payload.startswith(b"\x1f\x8b"):
        raise ValueError("download is too large or not gzip")
    # Validate gzip CRC/footer with a bounded decompression.
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as handle:
            if len(handle.read(12_000_001)) > 12_000_000:
                raise ValueError("decompressed export exceeds size cap")
    except (OSError, EOFError) as exc:
        raise ValueError("invalid gzip payload") from exc
    Path(destination).write_bytes(payload)
    return {"url": _BASE + name, "compressed_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def run(*, now=None, fetcher=fetch_public_file):
    now = now or datetime.now(timezone.utc)
    month = previous_month(now)
    with TemporaryDirectory() as tmp:
        paths = {name: Path(tmp) / name for name in _NAMES}
        sources = {name: fetcher(name, paths[name]) for name in _NAMES}
        for name in _NAMES:
            print("Public monthly CSV schema:", name, json.dumps(public_header_diagnostic(paths[name]), ensure_ascii=False))
        print("Public procurement date shapes:", json.dumps(public_date_diagnostic(paths["upphandlingar.csv.gz"]), ensure_ascii=False))
        segments = analyze_segments(paths["upphandlingar.csv.gz"], expected_month=month)
        subfamilies = analyze_subfamilies(paths["upphandlingar.csv.gz"], expected_month=month)
        supply = analyze_supply(paths["upphandlingar.csv.gz"], expected_month=month,
                                award_csv=paths["tilldelningar.csv.gz"])
        award_cpv = analyze_award_cpv(paths["upphandlingar.csv.gz"],
                                      paths["tilldelningar.csv.gz"], expected_month=month)
        if segments["rows"] == 0 or segments["rows"] != supply["procurement_rows"]:
            raise ValueError("empty or inconsistent procurement cohort")
        if subfamilies["procurement_rows"] != segments["rows"]:
            raise ValueError("CPV subfamily row reconciliation failed")
        for segment in ("48", "72"):
            if subfamilies["segment_any_notice_rows"].get(segment, 0) != segments["segments"][segment]["any_cpv_rows"]:
                raise ValueError("CPV subfamily segment reconciliation failed")
        if subfamilies["union_48_72_notice_rows"] != (
            segments["segments"]["48"]["any_cpv_rows"]
            + segments["segments"]["72"]["any_cpv_rows"]
            - segments["rows_with_both_48_and_72_any_cpv"]
        ):
            raise ValueError("CPV subfamily union reconciliation failed")
        if subfamilies["union_notices_covered_by_main_48_or_72"] != (
            supply["main_cpv48_rows"] + supply["main_cpv72_rows"]
        ):
            raise ValueError("broad main-CPV union coverage reconciliation failed")
        if subfamilies["union_notices_missed_by_main_48_or_72"] != (
            subfamilies["union_48_72_notice_rows"]
            - subfamilies["union_notices_covered_by_main_48_or_72"]
        ):
            raise ValueError("broad main-CPV union missingness reconciliation failed")
        for family in subfamilies["subfamilies"]:
            if (family["covered_by_main_union_rows"] + family["missed_by_main_union_rows"]
                    != family["notice_rows"]):
                raise ValueError("CPV family broad-union coverage reconciliation failed")
            if family["missed_by_main_union_rows"] > family["missed_by_main_segment_only_rows"]:
                raise ValueError("CPV family union cannot miss more than its own main segment")
            statuses = family["missed_union_status_rows_not_live"]
            sources = family["missed_union_source_rows"]
            if statuses is None or sources is None:
                if statuses is not None or sources is not None:
                    raise ValueError("inconsistent sparse missed-union breakdown")
                if family["missed_by_main_union_rows"] >= subfamilies["minimum_group_rows"]:
                    raise ValueError("missing non-sparse missed-union breakdown")
            elif (sum(statuses.values()) != family["missed_by_main_union_rows"]
                  or sum(sources.values()) != family["missed_by_main_union_rows"]):
                raise ValueError("CPV missed-union status/source reconciliation failed")
        if segments["segments"]["48"]["main_cpv_rows"] != supply["main_cpv48_rows"]:
            raise ValueError("CPV48 main-code reconciliation failed")
        if segments["segments"]["72"]["main_cpv_rows"] != supply["main_cpv72_rows"]:
            raise ValueError("CPV72 main-code reconciliation failed")
        if award_cpv["award_rows_joined_to_same_month_procurements"] != supply["award_file"]["award_rows_joined_to_same_month_procurements"]:
            raise ValueError("same-month award join reconciliation failed")
        return {
            "evidence_type": "public_monthly_publisher_rows_not_verified_buyer_demand",
            "retrieved_at_utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "publication_month": month,
            "source_page": "https://licitera.se/oppen-data",
            "license": "CC BY 4.0, public previous-month exports only",
            "attribution": "Licitera (licitera.se), CC BY 4.0; Uppgifter: Upphandlingsmyndigheten | Bearbetning: Licitera | Analys: AgentMine",
            "source_files": sources,
            "procurement_supply": supply,
            "cpv_segments": segments,
            "cpv_four_digit_subfamilies": subfamilies,
            "cpv_award_supplier_cohort": award_cpv,
            "verified_agentmine_customers": None,
            "verified_payment_conversion": None,
            "verified_agentmine_revenue": None,
            "warning": "Public monthly publisher cohort, not a national census. Buyer/supplier IDs are not verified companies, row shares are not market shares, awards may belong to earlier publication cohorts, and these records do not prove customer demand."
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Aggregate-only JSON; never raw files")
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Monthly public source analyzed:", report["publication_month"],
          "rows:", report["procurement_supply"]["procurement_rows"],
          "CPV48 any:", report["cpv_segments"]["segments"]["48"]["any_cpv_rows"],
          "CPV72 any:", report["cpv_segments"]["segments"]["72"]["any_cpv_rows"])
    niche = report["cpv_four_digit_subfamilies"]
    print("Broad main-CPV 48/72 union coverage:",
          niche["union_notices_covered_by_main_48_or_72"],
          "missed:", niche["union_notices_missed_by_main_48_or_72"])
    print("Four-digit main-segment search baseline:",
          json.dumps([
              {"cpv_prefix": g["cpv_four_digit_prefix"],
               "notice_rows": g["notice_rows"],
               "secondary_only_rows": g["secondary_only_rows"],
               "covered_by_main_segment_only_rows": g["covered_by_main_segment_only_rows"],
               "missed_by_main_segment_only_rows": g["missed_by_main_segment_only_rows"],
               "covered_by_main_union_rows": g["covered_by_main_union_rows"],
               "missed_by_main_union_rows": g["missed_by_main_union_rows"],
               "missed_union_status_rows_not_live": g["missed_union_status_rows_not_live"],
               "missed_union_source_rows": g["missed_union_source_rows"]}
              for g in niche["subfamilies"]
              if g["cpv_four_digit_prefix"] in {"7222", "7225", "7226", "7231"}
          ], ensure_ascii=False))


if __name__ == "__main__":
    main()
