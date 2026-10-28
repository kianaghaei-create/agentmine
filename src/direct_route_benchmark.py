"""Offline apples-to-apples direct vs. routed information cost benchmark.

Inputs are caller-submitted observations, never audited charges or buyer demand.
A quote comparison is a scenario, not a measured saving. No HTTP, payments,
credentials or user content are processed. All monetary values are USD strings.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from src.agentmine_cost_router import _public_source_url

_SHA = re.compile(r'^[0-9a-f]{64}$')
# Opaque, non-identifying task labels only; never echo free-form user IDs.
_TASK_ID = re.compile(r'^[Tt][0-9]{1,8}$')
_ALLOWED_FIELDS = frozenset(('task_id', 'mode', 'kind', 'task_spec_sha256',
                             'observed_at', 'evidence_url', 'license_allowed',
                             'source_usd', 'tokens_usd', 'network_usd',
                             'delivery_observed', 'output_sha256', 'latency_ms'))
_COMPONENTS = ('source_usd', 'tokens_usd', 'network_usd')


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('observed_at must be ISO 8601 string')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid observed_at') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('observed_at must include timezone')
    observed = dt.astimezone(timezone.utc)
    # A future observation cannot be evidence of completed delivery or cost.
    # Check both quoted and measured rows before any paired comparison.
    if observed > datetime.now(timezone.utc):
        raise ValueError('observed_at cannot be in the future')
    return observed


def _amount(value):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('cost must be exact nonnegative USD decimal')
    try:
        d = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError('invalid cost') from exc
    if not d.is_finite() or d < 0:
        raise ValueError('cost must be finite and nonnegative')
    return d


def _validate(row):
    if not isinstance(row, dict):
        raise ValueError('observation must be an object')
    if set(row) != _ALLOWED_FIELDS:
        raise ValueError('unexpected fields; do not submit identities or customer data')
    if row.get('mode') not in ('direct', 'routed') or row.get('kind') not in ('quoted', 'measured'):
        raise ValueError('invalid mode/kind')
    task = row.get('task_id')
    if not isinstance(task, str) or not _TASK_ID.fullmatch(task):
        raise ValueError('invalid task_id')
    if not _SHA.fullmatch(row.get('task_spec_sha256') or ''):
        raise ValueError('invalid task fingerprint')
    if row.get('license_allowed') is not True or not _public_source_url(row.get('evidence_url')):
        raise ValueError('license or evidence missing')
    timestamp = _utc(row.get('observed_at'))
    total = sum((_amount(row.get(k)) for k in _COMPONENTS), Decimal(0))
    kind = row['kind']
    if kind == 'measured':
        if row.get('delivery_observed') is not True or not _SHA.fullmatch(row.get('output_sha256') or ''):
            raise ValueError('measured delivery/digest missing')
        if type(row.get('latency_ms')) is not int or row['latency_ms'] < 0:
            raise ValueError('invalid measured latency')
    else:
        if row.get('delivery_observed') is not False or row.get('output_sha256') is not None or row.get('latency_ms') is not None:
            raise ValueError('quote cannot assert delivery or measured latency')
    return total, timestamp


def analyze(observations, *, max_gap_seconds=3600):
    """Only compare one direct and one routed observation for the same task.

    'measured' is still a caller assertion, NOT an independently verified bill.
    Comparisons with invalid provenance, licenses, output or timestamps are
    excluded rather than silently presented as cost savings.
    """
    if not isinstance(observations, list):
        raise ValueError('observations must be a list')
    if type(max_gap_seconds) is not int or not 0 <= max_gap_seconds <= 86400:
        raise ValueError('invalid max_gap_seconds')
    grouped = defaultdict(list)
    for index, row in enumerate(observations):
        task = row.get('task_id') if isinstance(row, dict) else None
        # Malformed task IDs are still visible in rejected counts without
        # risking accidental merging of unrelated records.
        # Never echo malformed caller IDs (which may contain PII) in output.
        safe_task = task if isinstance(task, str) and _TASK_ID.fullmatch(task) else f'__invalid_{index}'
        grouped[safe_task].append(row)
    pairs, rejected, counts = [], [], Counter()
    measured_total = Decimal(0)
    quoted_total = Decimal(0)
    for task, rows in sorted(grouped.items()):
        reason = None
        if (len(rows) != 2 or
                any(not isinstance(r, dict) or r.get('mode') not in ('direct', 'routed') for r in rows) or
                rows[0]['mode'] == rows[1]['mode']):
            reason = 'missing_or_duplicate_mode'
        else:
            try:
                left, right = sorted(rows, key=lambda r: r['mode'])
                lcost, lt = _validate(left)
                rcost, rt = _validate(right)
                if left['kind'] != right['kind']:
                    reason = 'mixed_quote_and_measurement'
                elif left['task_spec_sha256'] != right['task_spec_sha256']:
                    reason = 'different_task'
                elif left['kind'] == 'quoted' and left['evidence_url'] != right['evidence_url']:
                    # A quote has no delivered output to compare. A shared task
                    # fingerprint alone cannot establish the same source data.
                    reason = 'different_source_evidence_for_quote'
                elif abs((lt - rt).total_seconds()) > max_gap_seconds:
                    reason = 'time_window_mismatch'
                elif left['kind'] == 'measured' and left['output_sha256'] != right['output_sha256']:
                    reason = 'different_output'
                else:
                    delta = lcost - rcost
                    kind = left['kind']
                    result = {'task_id': task, 'kind': kind,
                              'direct_cost_usd': str(lcost), 'routed_cost_usd': str(rcost),
                              'direct_minus_routed_usd': str(delta),
                              'direct_minus_routed_pct': str(delta / lcost * 100) if lcost else None,
                              'evidence_type': ('caller_asserted_observed_delivery_and_cost'
                                                if kind == 'measured' else 'quoted_cost_scenario_not_savings'),
                              'independently_verified': False}
                    if kind == 'measured':
                        result['routed_minus_direct_latency_ms'] = right['latency_ms'] - left['latency_ms']
                        measured_total += delta
                    else:
                        result['routed_minus_direct_latency_ms'] = None
                        quoted_total += delta
                    pairs.append(result)
                    counts[kind] += 1
            except (ValueError, TypeError, KeyError) as exc:
                reason = 'invalid_observation'
        if reason:
            rejected.append({'task_id': task, 'reason': reason})
            counts['rejected'] += 1
    return {'measured_comparable_pairs': counts['measured'],
            'quoted_comparable_pairs': counts['quoted'],
            'rejected_tasks': rejected,
            'pairs': pairs,
            'caller_asserted_measured_delta_usd': str(measured_total) if counts['measured'] else None,
            'quoted_scenario_delta_usd': str(quoted_total) if counts['quoted'] else None,
            'verified_agentmine_revenue_usd': None,
            'verified_paying_customers': None,
            'warning': 'No independent verification of submitted measurements, prices, licenses or receipts. Quote deltas are not savings. Excludes CAC, infrastructure, support and compliance costs.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='local JSON list of paired observations')
    args = parser.parse_args(argv)
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding='utf-8'))), indent=2))


if __name__ == '__main__':
    main()
