"""Offline, source-bound x402 fact projection for agent context.

A projection is intentionally NOT equivalent to the full source for arbitrary
questions. Measures serialized UTF-8 bytes, never tokens, money, or demand.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import re
from pathlib import Path

SOURCE = 'https://x402-list.com/api/v1/stats'
PATH = re.compile(r'^(supply|activity_30d)\.[A-Za-z_][A-Za-z0-9_]*$')


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('source') != SOURCE:
        raise ValueError('unsupported source')
    if snapshot.get('license') != 'CC-BY-4.0' or not isinstance(snapshot.get('attribution'), str) or not snapshot['attribution'].strip():
        raise ValueError('source attribution and license required')
    if not isinstance(snapshot.get('market_scope'), str) or not snapshot['market_scope'].strip():
        raise ValueError('market scope required')
    if not isinstance(snapshot.get('evidence_type'), str) or not snapshot['evidence_type'].strip():
        raise ValueError('evidence classification required')
    for key in ('source_computed_at', 'traction_as_of'):
        stamp = snapshot.get(key)
        if not isinstance(stamp, str):
            raise ValueError('missing observation timestamp')
        try:
            dt = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        except ValueError as exc:
            raise ValueError('invalid observation timestamp') from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError('observation timestamp must have timezone')
    if not isinstance(snapshot.get('source_method_note'), str) or not snapshot['source_method_note'].strip():
        raise ValueError('methodology caveat required')
    caveats = snapshot.get('caveats')
    if not isinstance(caveats, list) or not caveats or any(not isinstance(c, str) or not c.strip() for c in caveats):
        raise ValueError('nonempty source caveats required')
    for section in ('supply', 'activity_30d'):
        if not isinstance(snapshot.get(section), dict):
            raise ValueError('missing facts section')
    _canonical(snapshot)  # Reject non-JSON / NaN before making comparisons.


def pack(snapshot, paths):
    """Preserve exact selected public facts and essential publisher caveats."""
    _validate_snapshot(snapshot)
    if not isinstance(paths, list) or not 1 <= len(paths) <= 32:
        raise ValueError('1..32 field paths required')
    facts = {}
    for path in paths:
        if not isinstance(path, str) or not PATH.fullmatch(path) or path in facts:
            raise ValueError('invalid or duplicate field path')
        section, field = path.split('.')
        if field not in snapshot[section]:
            raise ValueError('unknown field path')
        value = snapshot[section][field]
        if value is None or type(value) not in (str, int, float, bool):
            raise ValueError('missing or non-scalar fact')
        facts[path] = value
    result = {
        'source': snapshot['source'], 'license': snapshot['license'],
        'attribution': snapshot['attribution'],
        'source_computed_at': snapshot['source_computed_at'],
        'traction_as_of': snapshot['traction_as_of'],
        'market_scope': snapshot['market_scope'],
        'evidence_type': snapshot['evidence_type'],
        'source_method_note': snapshot['source_method_note'],
        'caveats': snapshot['caveats'],
        'selected_facts': facts,
        'source_record_canonical_sha256': sha256(_canonical(snapshot)).hexdigest(),
        'projection_scope': 'requested_fields_only_not_full_source_equivalence',
        'verified_paying_customers': None,
        'verified_agentmine_revenue_usd': None,
    }
    original_bytes = len(_canonical(snapshot))
    compact_bytes = len(_canonical(result))
    return {
        'context': result,
        'baseline_canonical_json_bytes': original_bytes,
        'projected_canonical_json_bytes': compact_bytes,
        'byte_difference': original_bytes - compact_bytes,
        'byte_reduction_pct': round(100 * (original_bytes - compact_bytes) / original_bytes, 2),
        'tokens_measured': False,
        'model_answer_quality_measured': False,
        'verified_cost_savings_usd': None,
        'verified_paying_customers': None,
        'warning': 'Task-specific projection; omitted fields may be necessary for other questions. Byte counts are NOT token or dollar savings. Publisher observations are not verified buyers.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--fields', nargs='+', required=True)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.input.read_text(encoding='utf-8'))
    print(json.dumps(pack(snapshot, args.fields), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
