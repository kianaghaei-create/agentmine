"""Offline byte-aware delivery decision for licensed, source-bound agent facts.

This is NOT a token optimizer. Only task-requested fields are covered by a
projection. Fall back to the original JSON when provenance overhead makes the
projection larger. The caller must independently validate task completeness,
answer quality and actual token/billing cost before claiming savings.
"""
import argparse
import json
from pathlib import Path

from src.x402_compact_context import pack


def choose_delivery(snapshot, fields):
    """Return a payload and byte comparison, never a claim of token savings."""
    trial = pack(snapshot, fields)  # validates provenance and requested paths
    smaller = trial['byte_difference'] > 0
    chosen = trial['context'] if smaller else snapshot
    return {
        'delivery_mode': 'requested_facts_projection' if smaller else 'original_source_fallback',
        'payload': chosen,
        'requested_fields': list(fields),
        'source_record_canonical_sha256': trial['context']['source_record_canonical_sha256'],
        'full_source_canonical_utf8_bytes': trial['baseline_canonical_json_bytes'],
        'projected_canonical_utf8_bytes': trial['projected_canonical_json_bytes'],
        'chosen_canonical_utf8_bytes': min(trial['baseline_canonical_json_bytes'],
                                            trial['projected_canonical_json_bytes']),
        'chosen_byte_difference': max(0, trial['byte_difference']),
        'projection_expands_bytes': trial['byte_difference'] < 0,
        'tokens_measured': False,
        'answer_quality_measured': False,
        'verified_cost_savings_usd': None,
        'verified_paying_customers': None,
        'warning': ('Payload byte comparison only; wrapper is excluded. Requested fields '
                    'are not proof of question coverage. Publisher-reported activity is '
                    'not verified customers or revenue.'),
    }


def benchmark_prefixes(snapshot, ordered_fields):
    """Measure ordered, cumulative task-field sets without inventing user demand."""
    if not isinstance(ordered_fields, list) or not ordered_fields:
        raise ValueError('nonempty ordered_fields required')
    rows = []
    for n in range(1, len(ordered_fields) + 1):
        result = choose_delivery(snapshot, ordered_fields[:n])
        rows.append({
            'field_count': n,
            'delivery_mode': result['delivery_mode'],
            'projected_canonical_utf8_bytes': result['projected_canonical_utf8_bytes'],
            'chosen_canonical_utf8_bytes': result['chosen_canonical_utf8_bytes'],
            'chosen_byte_difference': result['chosen_byte_difference'],
        })
    return {
        'source_record_canonical_sha256': result['source_record_canonical_sha256'],
        'full_source_canonical_utf8_bytes': result['full_source_canonical_utf8_bytes'],
        'prefix_results': rows,
        'tokens_measured': False,
        'answer_quality_measured': False,
        'verified_cost_savings_usd': None,
        'warning': 'Ordered field prefixes are constructed scenarios, not observed buyer tasks.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--fields', nargs='+', required=True)
    parser.add_argument('--prefix-benchmark', action='store_true')
    args = parser.parse_args(argv)
    snapshot = json.loads(args.input.read_text(encoding='utf-8'))
    result = (benchmark_prefixes(snapshot, args.fields) if args.prefix_benchmark
              else choose_delivery(snapshot, args.fields))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
