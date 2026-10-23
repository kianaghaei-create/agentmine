"""Fail-closed eligibility for x402 List service discovery snapshots.

A payment_ready badge is a 7-day-decay discovery signal, NOT evidence that a
service is online right now. No network, wallet, or payment operations.
"""
from datetime import datetime, timezone


def _utc(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def evaluate(service, *, observed_at, max_probe_age_seconds=3600):
    """Return route eligibility and reasons for one source-reported service.

    A fresh monitor success is NOT proof that a paid response will be delivered.
    Consumers must still check license, price, endpoint, and live behavior.
    """
    now = _utc(observed_at)
    if now is None:
        raise ValueError('observed_at must be timezone-aware ISO 8601')
    if type(max_probe_age_seconds) is not int or not 60 <= max_probe_age_seconds <= 86400:
        raise ValueError('max_probe_age_seconds must be integer in 60..86400')
    if not isinstance(service, dict):
        raise ValueError('service must be object')
    reasons = []
    if service.get('status') != 'online':
        reasons.append('not_currently_online')
    if service.get('payment_ready') is not True:
        reasons.append('payment_readiness_not_confirmed')
    checked = _utc(service.get('last_checked_at'))
    if checked is None:
        reasons.append('missing_or_invalid_last_check')
    else:
        age = (now - checked).total_seconds()
        if age < 0:
            reasons.append('last_check_in_future')
        elif age > max_probe_age_seconds:
            reasons.append('last_check_stale')
    assessment = service.get('assessment')
    if not isinstance(assessment, dict):
        reasons.append('missing_assessment')
    else:
        compliance = assessment.get('compliance')
        stale = compliance.get('staleness') if isinstance(compliance, dict) else None
        if not isinstance(stale, dict) or stale.get('probe_failing') is not False:
            reasons.append('probe_failure_or_unknown')
        else:
            last_success = _utc(stale.get('last_success_at'))
            if last_success is None:
                reasons.append('missing_or_invalid_last_success')
            else:
                age = (now - last_success).total_seconds()
                if age < 0:
                    reasons.append('last_success_in_future')
                elif age > max_probe_age_seconds:
                    reasons.append('last_success_stale')
    return {
        'eligible_for_live_route_candidate': not reasons,
        'reasons': reasons,
        'source': 'https://x402-list.com/api/v1/services',
        'observed_at': now.isoformat(),
        'evidence_type': 'publisher_monitoring_not_paid_delivery_proof',
        'verified_customer_count': None,
        'warning': 'A fresh payment-ready online service is a candidate, not a verified deliverable, authorized source, or paying customer.',
    }
