"""Offline paired-task evaluation for an opt-in supplier preflight pilot.

No customer identity or procurement text is accepted. This is descriptive
self-reported evidence, not independently verified demand or a sales claim.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from statistics import median

_TASK = re.compile(r"^T[0-9]{3,8}$")
_ALLOWED_TOP = {"evidence_type", "sample_kind", "observed_at_utc", "tasks"}
_ALLOWED_TASK = {"task_id", "consent_recorded", "baseline_minutes", "agent_minutes",
                 "baseline_correct", "agent_correct", "primary_source_checked",
                 "incremental_variable_cost_sek"}


def _decimal(value, name, *, positive=False):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{name} must be exact decimal text or integer")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def evaluate(snapshot, *, hourly_labor_cost_sek, value_capture_pct="25", min_tasks=5):
    """Compute paired descriptive economics without inferring WTP or retention."""
    if not isinstance(snapshot, dict) or set(snapshot) != _ALLOWED_TOP:
        raise ValueError("unexpected or missing top-level fields; do not submit personal data")
    if snapshot['evidence_type'] != 'paired_supplier_preflight_pilot':
        raise ValueError("unsupported evidence type")
    if snapshot['sample_kind'] not in ('synthetic', 'self_reported_consented'):
        raise ValueError("unknown sample kind")
    try:
        stamp = datetime.fromisoformat(snapshot['observed_at_utc'].replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc
    if stamp.utcoffset() is None or stamp > datetime.now(timezone.utc):
        raise ValueError("timestamp must be offset-aware and not future-dated")
    hourly = _decimal(hourly_labor_cost_sek, 'hourly_labor_cost_sek', positive=True)
    capture = _decimal(value_capture_pct, 'value_capture_pct', positive=True)
    if capture > 100:
        raise ValueError("value_capture_pct exceeds 100")
    if type(min_tasks) is not int or min_tasks < 1:
        raise ValueError("min_tasks must be a positive integer")
    tasks = snapshot['tasks']
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 1000:
        raise ValueError("tasks must be a nonempty bounded list")
    ids = set()
    deltas = []
    costs = Decimal(0)
    correctness_regressions = 0
    agent_errors = 0
    unchecked = 0
    for row in tasks:
        if not isinstance(row, dict) or set(row) != _ALLOWED_TASK:
            raise ValueError("unexpected task fields; no identities or tender text allowed")
        task_id = row['task_id']
        if not isinstance(task_id, str) or not _TASK.fullmatch(task_id) or task_id in ids:
            raise ValueError("task IDs must be unique opaque T-prefixed numbers")
        ids.add(task_id)
        if row['consent_recorded'] is not True:
            raise ValueError("explicit task consent required")
        for flag in ('baseline_correct', 'agent_correct', 'primary_source_checked'):
            if type(row[flag]) is not bool:
                raise ValueError(f"{flag} must be boolean")
        baseline = _decimal(row['baseline_minutes'], 'baseline_minutes')
        agent = _decimal(row['agent_minutes'], 'agent_minutes')
        if baseline > 480 or agent > 480:
            raise ValueError("task time exceeds 480 minute pilot limit")
        costs += _decimal(row['incremental_variable_cost_sek'], 'incremental_variable_cost_sek')
        deltas.append(baseline - agent)
        correctness_regressions += int(row['baseline_correct'] and not row['agent_correct'])
        agent_errors += int(not row['agent_correct'])
        unchecked += int(not row['primary_source_checked'])
    total_minutes = sum(deltas, Decimal(0))
    net_value = total_minutes * hourly / Decimal(60) - costs
    # Synthetic arithmetic fixtures must never pass an evidence-based pilot gate.
    # Self-reported consent and correctness are still NOT independently verified.
    sample_gate = (snapshot['sample_kind'] == 'self_reported_consented'
                   and len(tasks) >= min_tasks and agent_errors == 0 and unchecked == 0)
    economic_screen = sample_gate and total_minutes > 0 and net_value > 0
    return {
        'sample_kind': snapshot['sample_kind'],
        'source_observed_at_utc': snapshot['observed_at_utc'],
        'paired_task_count': len(tasks),
        'total_incremental_minutes_saved': str(total_minutes),
        'mean_incremental_minutes_saved': str(total_minutes / len(tasks)),
        'median_incremental_minutes_saved': str(median(deltas)),
        'faster_task_count': sum(delta > 0 for delta in deltas),
        'slower_task_count': sum(delta < 0 for delta in deltas),
        'correctness_regression_count': correctness_regressions,
        'agent_error_count': agent_errors,
        'primary_source_unchecked_count': unchecked,
        'scenario_hourly_labor_cost_sek': str(hourly),
        'scenario_value_capture_pct': str(capture),
        'observed_or_declared_variable_cost_sek': str(costs),
        'scenario_net_labor_value_sek': str(net_value),
        'scenario_max_software_price_per_task_sek': str(max(Decimal(0), net_value * capture / (Decimal(100) * len(tasks)))),
        'minimum_sample_quality_gate_met': sample_gate,
        'self_reported_positive_economic_screen_met': economic_screen,
        'commercial_validation_status': 'NOT_VALIDATED',
        'verified_willingness_to_pay': None,
        'verified_paying_customers': None,
        'verified_revenue_sek': None,
        'warning': 'Consent, correctness, source review and time are self-declared; synthetic samples prove no demand. '
                   'The self-reported quality/economic screens never establish willingness to pay, independent validation or permission to deploy. '
                   'Do not extrapolate without representative repeated tasks and independently checked outcomes.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--hourly-cost-sek', required=True)
    parser.add_argument('--value-capture-pct', default='25')
    parser.add_argument('--min-tasks', type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text(encoding='utf-8')),
                              hourly_labor_cost_sek=args.hourly_cost_sek,
                              value_capture_pct=args.value_capture_pct,
                              min_tasks=args.min_tasks), indent=2))


if __name__ == '__main__':
    main()
