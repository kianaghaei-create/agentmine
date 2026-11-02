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
_UTC_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$")
_ALLOWED_TOP = {"evidence_type", "sample_kind", "observed_at_utc", "tasks"}
_ALLOWED_TOP_WITH_RESPONSES = _ALLOWED_TOP | {"price_responses"}
_ALLOWED_RESPONSE = {"response_id", "consent_recorded", "response_kind", "quoted_monthly_price_sek"}
_RESPONSE_ID = re.compile(r"^R[0-9]{3,8}$")
_PAID_RESPONSES = {"accepted_paid_pilot", "declined_paid_pilot"}
_OTHER_RESPONSES = {"free_pilot_only", "undecided", "no_response"}
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


def _price_response_counts(rows):
    """Summarize anonymized, self-declared replies; not unique verified buyers."""
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError("price_responses must be a bounded list")
    counts = {kind: 0 for kind in sorted(_PAID_RESPONSES | _OTHER_RESPONSES)}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != _ALLOWED_RESPONSE:
            raise ValueError("unexpected price response fields; no identities allowed")
        identifier = row["response_id"]
        if (not isinstance(identifier, str) or not _RESPONSE_ID.fullmatch(identifier)
                or identifier in seen):
            raise ValueError("response IDs must be unique opaque R-prefixed numbers")
        seen.add(identifier)
        kind = row["response_kind"]
        if not isinstance(kind, str) or kind not in counts:
            raise ValueError("unknown price response kind")
        consent = row["consent_recorded"]
        if type(consent) is not bool:
            raise ValueError("consent_recorded must be boolean")
        # Nonrespondents cannot consent to storing a reply. Keep their opaque
        # invitation outcomes in the denominator without inventing consent.
        # Every actual reply still requires explicit consent.
        if kind != "no_response" and not consent:
            raise ValueError("consent required for response evidence")
        price = row["quoted_monthly_price_sek"]
        if kind in _PAID_RESPONSES:
            _decimal(price, "quoted_monthly_price_sek", positive=True)
        elif price is not None:
            raise ValueError("non-paid response must not assert a quoted price")
        counts[kind] += 1
    return counts


def evaluate(snapshot, *, hourly_labor_cost_sek, value_capture_pct="25", min_tasks=5):
    """Compute paired descriptive economics without inferring WTP or retention."""
    if not isinstance(snapshot, dict) or set(snapshot) not in (_ALLOWED_TOP, _ALLOWED_TOP_WITH_RESPONSES):
        raise ValueError("unexpected or missing top-level fields; do not submit personal data")
    if snapshot['evidence_type'] != 'paired_supplier_preflight_pilot':
        raise ValueError("unsupported evidence type")
    if snapshot['sample_kind'] not in ('synthetic', 'self_reported_consented'):
        raise ValueError("unknown sample kind")
    observed = snapshot['observed_at_utc']
    if not isinstance(observed, str) or not _UTC_STAMP.fullmatch(observed):
        raise ValueError("timestamp must use canonical UTC ISO-8601")
    try:
        stamp = datetime.fromisoformat(observed.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if stamp > datetime.now(timezone.utc):
        raise ValueError("timestamp must not be future-dated")
    hourly = _decimal(hourly_labor_cost_sek, 'hourly_labor_cost_sek', positive=True)
    capture = _decimal(value_capture_pct, 'value_capture_pct', positive=True)
    if capture > 100:
        raise ValueError("value_capture_pct exceeds 100")
    # The predeclared commercial pilot requires at least five genuine paired
    # tasks. CLI callers must not lower that floor to make a small sample pass.
    if type(min_tasks) is not int or min_tasks < 5:
        raise ValueError("min_tasks must be an integer >= 5 for the pilot gate")
    tasks = snapshot['tasks']
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 1000:
        raise ValueError("tasks must be a nonempty bounded list")
    ids = set()
    deltas = []
    costs = Decimal(0)
    correctness_regressions = 0
    baseline_errors = 0
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
        baseline_errors += int(not row['baseline_correct'])
        agent_errors += int(not row['agent_correct'])
        unchecked += int(not row['primary_source_checked'])
    responses = _price_response_counts(snapshot.get("price_responses", []))
    explicit_responses = sum(responses[k] for k in (
        "accepted_paid_pilot", "declined_paid_pilot", "free_pilot_only"))
    total_minutes = sum(deltas, Decimal(0))
    net_value = total_minutes * hourly / Decimal(60) - costs
    # Synthetic arithmetic fixtures must never pass an evidence-based pilot gate.
    # Self-reported consent and correctness are still NOT independently verified.
    sample_gate = (snapshot['sample_kind'] == 'self_reported_consented'
                   and len(tasks) >= min_tasks and baseline_errors == 0
                   and agent_errors == 0 and unchecked == 0)
    # A single unusually large win must not mask a pilot where most tasks
    # became slower. Keep aggregate economics visible, but use a conservative
    # majority-of-pairs condition for the positive self-reported screen.
    faster_count = sum(delta > 0 for delta in deltas)
    slower_count = sum(delta < 0 for delta in deltas)
    majority_faster = faster_count * 2 > len(tasks)
    aggregate_positive = sample_gate and total_minutes > 0 and net_value > 0
    economic_screen = aggregate_positive and majority_faster
    # A fast but incorrect or source-unchecked answer has no defensible
    # labor-value price ceiling. Preserve raw arithmetic for diagnostics,
    # but fail closed on the monetization scenario itself.
    price_eligible = baseline_errors == 0 and agent_errors == 0 and unchecked == 0
    scenario_price = (str(max(Decimal(0), net_value * capture /
                              (Decimal(100) * len(tasks)))) if price_eligible else None)
    return {
        'sample_kind': snapshot['sample_kind'],
        'price_response_count': sum(responses.values()),
        'explicit_price_or_pilot_response_count': explicit_responses,
        'self_reported_paid_pilot_yes_count': responses["accepted_paid_pilot"],
        'self_reported_paid_pilot_no_count': responses["declined_paid_pilot"],
        'self_reported_free_pilot_only_count': responses["free_pilot_only"],
        'self_reported_undecided_count': responses["undecided"],
        'self_reported_no_response_count': responses["no_response"],
        'three_explicit_responses_screen_met': (
            snapshot['sample_kind'] == 'self_reported_consented'
            and explicit_responses >= 3),
        'verified_distinct_respondents': None,
        'source_observed_at_utc': snapshot['observed_at_utc'],
        'paired_task_count': len(tasks),
        'total_incremental_minutes_saved': str(total_minutes),
        'mean_incremental_minutes_saved': str(total_minutes / len(tasks)),
        'median_incremental_minutes_saved': str(median(deltas)),
        'faster_task_count': faster_count,
        'slower_task_count': slower_count,
        'majority_of_tasks_faster_screen_met': majority_faster,
        'aggregate_positive_but_majority_not_faster': aggregate_positive and not majority_faster,
        'correctness_regression_count': correctness_regressions,
        'baseline_error_count': baseline_errors,
        'agent_error_count': agent_errors,
        'primary_source_unchecked_count': unchecked,
        'scenario_hourly_labor_cost_sek': str(hourly),
        'scenario_value_capture_pct': str(capture),
        'observed_or_declared_variable_cost_sek': str(costs),
        'scenario_net_labor_value_sek': str(net_value),
        'scenario_max_software_price_per_task_sek': scenario_price,
        'scenario_price_suppressed_reason': (None if price_eligible else
                                             'incorrect_or_source_unchecked_task_outcomes'),
        'minimum_sample_quality_gate_met': sample_gate,
        'self_reported_positive_economic_screen_met': economic_screen,
        'commercial_validation_status': 'NOT_VALIDATED',
        'verified_willingness_to_pay': None,
        'verified_paying_customers': None,
        'verified_revenue_sek': None,
        'warning': 'Consent, correctness, source review and time are self-declared; synthetic samples prove no demand. '
                   'Time deltas from incorrect baselines are not comparable savings; incorrect or source-unchecked outcomes suppress the scenario price ceiling. '
                   'The self-reported quality/economic/price-response screens never establish verified distinct buyers, willingness to pay, independent validation or permission to deploy. '
                   'The positive economic screen additionally requires a strict majority of paired tasks to be faster; an aggregate win driven by one outlier is insufficient. '
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
