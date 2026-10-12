"""Offline CPV category evidence from saved TED snapshots, never buyer/payment proof.

Input is a snapshot from src.ted_notice_evidence.collect. Counts are notices,
not unique procurements, awarded contracts, supplier sales or AgentMine users.
Incomplete snapshots describe only the observed sample, not the query universe.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

_CPV = re.compile(r"^[0-9]{8}$")


def _cpvs(value):
    if value is None:
        return set()
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        raw = value
    else:
        raise ValueError("unsupported classification-cpv structure")
    result = set()
    for code in raw:
        code = code.strip()
        if not _CPV.fullmatch(code):
            raise ValueError("invalid CPV code")
        result.add(code)
    return result


def _buyer_label(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().casefold() or None
    if isinstance(value, dict):
        names = []
        for key in sorted(value):
            item = value[key]
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, list) and all(isinstance(v, str) for v in item):
                names.extend(item)
            else:
                raise ValueError("unsupported buyer-name structure")
        normalized = sorted({n.strip().casefold() for n in names if n.strip()})
        # A multilingual object can contain translations of one organization.
        # Pick a deterministic label, but never assert legal-entity uniqueness.
        return normalized[0] if normalized else None
    raise ValueError("unsupported buyer-name structure")


def summarize(snapshot, *, min_notices=1):
    if type(min_notices) is not int or min_notices < 1:
        raise ValueError("min_notices must be a positive integer")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("notices"), list):
        raise ValueError("invalid snapshot")
    rows = snapshot["notices"]
    if type(snapshot.get("complete")) is not bool:
        raise ValueError("snapshot completeness must be boolean")
    if type(snapshot.get("unique_notices_collected")) is not int or snapshot["unique_notices_collected"] != len(rows):
        raise ValueError("invalid unique_notices_collected")
    if snapshot.get("source_url") != "https://api.ted.europa.eu/v3/notices/search":
        raise ValueError("unexpected TED source")
    if not isinstance(snapshot.get("observed_at"), str) or not snapshot["observed_at"]:
        raise ValueError("missing observed_at")
    ids = set()
    groups = defaultdict(list)
    type_counts = Counter()
    missing_cpv = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("notice must be object")
        identifier = row.get("publication-number")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
            raise ValueError("missing/duplicate publication-number")
        ids.add(identifier)
        kind = row.get("notice-type")
        if kind is not None and not isinstance(kind, str):
            raise ValueError("invalid notice-type")
        if kind is None:
            family = "unknown"
        elif kind.startswith("cn-"):
            family = "contract_notice"
        elif kind.startswith("can-"):
            family = "contract_award"
        else:
            family = "other"
        type_counts[family] += 1
        codes = _cpvs(row.get("classification-cpv"))
        if family != "contract_notice":
            continue
        if not codes:
            missing_cpv += 1
        buyer = _buyer_label(row.get("buyer-name"))
        # One notice may have many codes, but contributes once per CPV division.
        for division in {code[:2] for code in codes}:
            groups[division].append((identifier, buyer))
    categories = []
    for division, entries in sorted(groups.items()):
        if len(entries) < min_notices:
            continue
        buyers = Counter(b for _, b in entries if b is not None)
        labeled = sum(buyers.values())
        categories.append({
            "cpv_division_prefix": division,
            "contract_notice_count_in_sample": len(entries),
            "buyer_label_coverage": round(labeled / len(entries), 4),
            "distinct_unverified_buyer_labels": len(buyers),
            "largest_buyer_label_notice_share": round(max(buyers.values()) / labeled, 4) if labeled else None,
            "buyer_label_hhi_in_labeled_sample": round(sum((n / labeled)**2 for n in buyers.values()), 4) if labeled else None,
        })
    categories.sort(key=lambda r: (-r["contract_notice_count_in_sample"], r["cpv_division_prefix"]))
    return {
        "source_url": snapshot["source_url"], "observed_at": snapshot["observed_at"],
        "query": snapshot.get("query"), "complete_for_query": snapshot["complete"],
        "sample_notice_count": len(rows), "notice_family_counts": dict(sorted(type_counts.items())),
        "contract_notices_without_cpv": missing_cpv,
        "categories": categories,
        "verified_distinct_buyers": None, "verified_payments": None,
        "agentmine_revenue": None,
        "warning": "Counts describe published notices, not unique purchasing decisions or paying AgentMine customers. "
                   "Buyer labels are unverified, categories overlap, and incomplete crawls are samples only. "
                   "Contract notices may be withdrawn, amended or duplicated as procedures."
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--min-notices", type=int, default=1)
    args = p.parse_args()
    print(json.dumps(summarize(json.loads(args.input.read_text(encoding="utf-8")),
                               min_notices=args.min_notices), indent=2))


if __name__ == "__main__":
    main()
