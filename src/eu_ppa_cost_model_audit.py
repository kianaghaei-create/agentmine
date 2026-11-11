"""Reproduce selected official impact-assessment cost denominators offline.

The common-denominator figures are diagnostics, not corrected forecasts or
observed supplier savings. Do not use the mixed-unit headline as a price anchor.
"""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

EVIDENCE = "data/evidence/eu_ppa_impact_cost_denominators_2026-11-11.json"
SOURCE = "https://data.consilium.europa.eu/doc/document/ST-12969-2026-ADD-3/en/pdf"


def _positive(row, key):
    value = row.get(key)
    if type(value) is not int or value <= 0:
        raise ValueError("invalid positive integer: " + key)
    return Decimal(value)


def _decimal(row, key, expected):
    value = row.get(key)
    if type(value) is not str or value != expected:
        raise ValueError("unbound model denominator: " + key)
    return Decimal(value)


def _show(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def analyze(snapshot):
    if not isinstance(snapshot, dict) or (snapshot.get("evidence_type"), snapshot.get("source_url"),
            snapshot.get("document"), snapshot.get("basis")) != (
            "official_impact_assessment_model_not_observed_savings", SOURCE, "SWD(2026) 591 final",
            "annualised_present_value_seven_years_3_percent_discount_model"):
        raise ValueError("unbound impact assessment or evidence basis")
    b, p, m = (snapshot.get(k) for k in ("baseline", "preferred_option", "digital_marketplace_mpl1"))
    if not all(isinstance(row, dict) for row in (b, p, m)):
        raise ValueError("missing cost model sections")
    notices = _positive(b, "contract_award_notices")
    bids = _decimal(b, "average_bids_per_notice", "3.3")
    ratio = _decimal(b, "reported_operator_to_winner_ratio", "2.15")
    operators = _positive(b, "estimated_distinct_operators")
    winners = _positive(b, "winning_operators")
    baseline = _positive(b, "above_eu_threshold_2019_2024_supplier_cost_eur")
    if (operators / winners).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != ratio:
        raise ValueError("operator/winner ratio does not reconcile")
    eo = _positive(p, "annual_supplier_savings_eur")
    ca = _positive(p, "annual_buyer_savings_eur")
    net = _positive(p, "annual_total_net_savings_eur")
    if eo + ca - _positive(p, "annual_member_state_cost_eur") - _positive(p, "annual_commission_cost_eur") != net:
        raise ValueError("annual aggregate does not reconcile")
    headline = _positive(p, "reported_supplier_per_procedure_savings_eur")
    components = p.get("reported_supplier_component_savings_eur")
    if not isinstance(components, list) or len(components) != 5 or any(type(v) is not int for v in components) or sum(components) != headline:
        raise ValueError("reported mixed-unit components do not reconcile")
    mpl = _positive(m, "annual_supplier_savings_eur")
    mpl_reported = _positive(m, "reported_supplier_per_procedure_savings_eur")
    if m.get("denominator") != "contract_award_notices_times_operator_to_winner_ratio" or components[-1] != mpl_reported:
        raise ValueError("MPL.1 denominator or component mismatch")
    mpl_ratio = mpl / (notices * ratio)
    if abs(mpl_ratio - mpl_reported) > 1:
        raise ValueError("MPL.1 reported amount does not reconcile within rounding")
    per_entity = eo / operators
    if abs(per_entity - _positive(p, "reported_supplier_annual_per_entity_savings_eur")) > 1:
        raise ValueError("annual per-entity amount does not reconcile within rounding")
    reported_pct = _decimal(p, "reported_supplier_savings_pct", "8.9")
    if (headline / baseline * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) != reported_pct:
        raise ValueError("reported headline percentage does not reconcile")
    combined = (eo + ca) / notices
    if abs(combined - _positive(p, "reported_combined_per_procedure_savings_eur")) > 2:
        raise ValueError("combined buyer/supplier amount does not reconcile within rounding")
    common = eo / (notices * bids)
    return {
        "source_url": SOURCE, "reported_mpl1_per_procedure_eur": int(mpl_reported),
        "reproduced_mpl1_using_2_15_ratio_eur": _show(mpl_ratio),
        "diagnostic_mpl1_using_3_3_bids_eur": _show(mpl / (notices * bids)),
        "reported_preferred_supplier_per_procedure_eur": int(headline),
        "diagnostic_preferred_using_3_3_bids_eur": _show(common),
        "reported_preferred_supplier_pct": str(reported_pct),
        "diagnostic_common_denominator_pct": _show(common / baseline * 100),
        "reproduced_annual_supplier_per_entity_eur": _show(per_entity),
        "reproduced_combined_buyer_supplier_per_procedure_eur": _show(combined),
        "mixed_denominators": True, "headline_usable_as_agentmine_price_anchor": False,
        "observed_agentmine_savings": None, "verified_agentmine_revenue": None,
        "warning": "Diagnostic normalisation only; not a corrected impact forecast, current customer cost or willingness to pay.",
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(analyze(json.loads((root / EVIDENCE).read_text(encoding="utf-8"))), indent=2))
