"""Offline CPV bid-intensity vintage audit; never infer buyer demand from bid means.

Source observations are manually transcribed from official UHM report tables.
This tool does not query TED, infer tender counts, or establish AgentMine revenue.
"""
from decimal import Decimal, InvalidOperation

SOURCES = {
    'uhm_report_2024': {
        'url': 'https://www.upphandlingsmyndigheten.se/globalassets/dokument/publikationer/rapport-om-utvecklingen-pa-upphandlingsomradet-2024-2.pdf',
        'vintage': 2025,
        'latest_reference_year': 2023,
    },
    'uhm_report_2025': {
        'url': 'https://www.upphandlingsmyndigheten.se/globalassets/dokument/publikationer/rapport-om-utvecklingen-pa-upphandlingsomradet-2025.pdf',
        'vintage': 2026,
        'latest_reference_year': 2024,
    },
}
CPVS = ('48', '72')


def _mean(value):
    if type(value) is not str:
        raise ValueError('mean must be a decimal string')
    try:
        n = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('invalid mean') from exc
    if not n.is_finite() or n < 0 or n >= 100 or n.as_tuple().exponent != -1:
        raise ValueError('mean must be a nonnegative, one-decimal number below 100')
    return n


def analyze(evidence):
    """Prefer latest official report vintage; expose retrospective revisions explicitly."""
    if (not isinstance(evidence, dict) or evidence.get('source_kind') != 'official_published_aggregate'
            or evidence.get('bid_count_coverage_by_cpv_verified') is not False
            or evidence.get('paying_buyers_verified') is not False):
        raise ValueError('unsupported evidence type or unverifiable coverage claims')
    rows = evidence.get('observations')
    if not isinstance(rows, list) or not rows:
        raise ValueError('missing observations')
    by_key = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid observation')
        sid, year, cpv = row.get('source_id'), row.get('reference_year'), row.get('cpv')
        if sid not in SOURCES or type(year) is not int or year not in (2021, 2022, 2023, 2024) or cpv not in CPVS:
            raise ValueError('unsupported report/year/CPV')
        source = SOURCES[sid]
        if (row.get('source_url') != source['url'] or year > source['latest_reference_year']
                or type(row.get('pdf_page')) is not int or row['pdf_page'] < 1):
            raise ValueError('invalid source provenance')
        val = _mean(row.get('mean_bids'))
        key = (cpv, year)
        entries = by_key.setdefault(key, {})
        if sid in entries:
            raise ValueError('duplicate CPV/year/source')
        entries[sid] = val
    # Require both categories and both years in latest source; no spliced trends.
    selected = {}
    for cpv in CPVS:
        for year in (2023, 2024):
            entry = by_key.get((cpv, year), {})
            if 'uhm_report_2025' not in entry:
                raise ValueError('missing latest-vintage comparable year')
            selected[(cpv, year)] = entry['uhm_report_2025']
    revisions = []
    for (cpv, year), entries in sorted(by_key.items()):
        if len(entries) == 2 and len(set(entries.values())) > 1:
            revisions.append({'cpv': cpv, 'reference_year': year,
                              'previous_report_mean': str(entries['uhm_report_2024']),
                              'latest_report_mean': str(entries['uhm_report_2025']),
                              'revision_bids_per_procurement': str(entries['uhm_report_2025'] - entries['uhm_report_2024'])})
    latest_48, latest_72 = selected[('48', 2024)], selected[('72', 2024)]
    def change(cpv):
        return selected[(cpv, 2024)] - selected[(cpv, 2023)]
    return {
        'source_kind': 'official_published_aggregate',
        'preferred_vintage': 'uhm_report_2025 (published 2026)',
        'cpv48_2023_mean': str(selected[('48', 2023)]),
        'cpv48_2024_mean': str(latest_48),
        'cpv72_2023_mean': str(selected[('72', 2023)]),
        'cpv72_2024_mean': str(latest_72),
        'cpv48_2023_to_2024_change': str(change('48')),
        'cpv72_2023_to_2024_change': str(change('72')),
        'cpv72_minus_cpv48_2024': str(latest_72 - latest_48),
        'cpv48_to_cpv72_2024_ratio': str((latest_48 / latest_72).quantize(Decimal('0.001'))) if latest_72 else None,
        'retrospective_revisions': revisions,
        'cpv_bid_count_coverage': None,
        'cpv48_one_bid_share': None,
        'distinct_suppliers': None,
        'verified_paying_buyers': None,
        'agentmine_revenue': None,
        'warning': ('These are published bid means for cohorts with unknown CPV-specific coverage. '
                    'Low bid means do not prove unmet supplier demand, one-bid frequency, '
                    'market size, concentration, or payment willingness. Never splice report vintages.'),
    }
