"""Audit a selected official PPDS award and distinguish public baseline from requirements.

Offline evidence arithmetic only: no payment, delivery, renewal or buyer validation.
"""
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

EVIDENCE = "data/evidence/ppds_awarded_quality_scope_2026-11-11.json"
AWARD_URL = "https://ted.europa.eu/en/notice/34077-2026/html"
SPEC_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/docs/1837c208-7869-4190-bf65-3bccd8a1f919-CN/ANNEX%20I%20-%20Annex%20I.a%20Tender%20specifications%20EC-GROW2025OP0002%20Part%202_V1.pdf"
DQ_URL = "https://eproc.pages.code.europa.eu/ppds/pages/Data-Quality/"
VIEW_URL = "https://op.europa.eu/en/web/about-us/public-procurement-procedure-view"
CAPABILITIES = {
    "source_data_quality": ("documented_existing", DQ_URL),
    "procedure_linkage_and_curation": ("documented_existing", DQ_URL),
    "public_procedure_view": ("documented_existing", VIEW_URL),
    "lifecycle_monitoring_and_source_field_mapping": ("awarded_contract_requirement", SPEC_URL),
    "prepublication_quality_api": ("awarded_contract_requirement", SPEC_URL),
    "open_source_artifacts": ("awarded_contract_requirement", SPEC_URL),
}


def _day(value):
    try:
        result = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid calendar date") from exc
    if result.isoformat() != value:
        raise ValueError("date must be ISO YYYY-MM-DD")
    return result


def _integer(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError("invalid integer amount or count")
    return value


def _pct(numerator, denominator):
    return Decimal(100 * numerator) / Decimal(denominator)


def _display(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def analyze(snapshot):
    """Validate the reviewed record and preserve the evidence boundaries."""
    if not isinstance(snapshot, dict) or snapshot.get("evidence_type") != "selected_ppds_award_and_public_baseline":
        raise ValueError("expected reviewed PPDS evidence")
    a = snapshot.get("award")
    if not isinstance(a, dict) or (
        a.get("source_url"), a.get("publication_number"), a.get("procedure_id"),
        a.get("contract_id"), a.get("reference"), a.get("currency"), a.get("amount_basis")
    ) != (AWARD_URL, "34077-2026", "1837c208-7869-4190-bf65-3bccd8a1f919",
          "300133376", "EC-GROW/2025/OP/0002", "EUR", "published_contract_award_value_not_cash"):
        raise ValueError("unbound award identity or financial basis")
    if not (_day(a.get("winner_selected_on")) <= _day(a.get("contract_concluded_on"))
            <= _day(a.get("published_on")) <= _day(snapshot.get("observed_on"))):
        raise ValueError("invalid award chronology")
    for key in ("actual_cash_paid_eur", "qa_only_contract_value_eur", "renewals_exercised"):
        if key not in a or a[key] is not None:
            raise ValueError("unsupported financial or renewal inference")
    if a.get("subcontract_percentage_denominator_verified") is not False:
        raise ValueError("subcontract denominator not verified")
    estimate = _integer(a.get("estimate_eur"))
    award = _integer(a.get("award_value_eur"))
    if _integer(a.get("winning_tender_value_eur")) != award:
        raise ValueError("single-lot award/tender value mismatch")
    sub = _integer(a.get("subcontract_value_eur"))
    reported = _integer(a.get("subcontract_reported_pct"), 0)
    if sub > award or reported > 100:
        raise ValueError("invalid subcontract amount or percentage")
    tenders = _integer(a.get("electronic_tenders_received"))
    initial = _integer(a.get("initial_months"))
    maximum = _integer(a.get("maximum_months"))
    renewals = _integer(a.get("maximum_renewals"), 0)
    if maximum != initial * (1 + renewals):
        raise ValueError("inconsistent stated maximum term")
    if _integer(a.get("quality_weight_pct"), 0) + _integer(a.get("price_weight_pct"), 0) != 100:
        raise ValueError("invalid award criteria weights")
    seen = {}
    capabilities = snapshot.get("capabilities")
    if not isinstance(capabilities, list):
        raise ValueError("missing capability evidence")
    for row in capabilities:
        if not isinstance(row, dict):
            raise ValueError("invalid capability")
        key = row.get("id")
        if key in seen or CAPABILITIES.get(key) != (row.get("status"), row.get("source_url")):
            raise ValueError("duplicate, unbound or overstated capability")
        if not isinstance(row.get("locator"), str) or not row["locator"].strip():
            raise ValueError("missing source locator")
        seen[key] = row["status"]
    if set(seen) != set(CAPABILITIES):
        raise ValueError("incomplete baseline")
    sub_award = _pct(sub, award)
    sub_estimate = _pct(sub, estimate)
    return {
        "award_value_eur": award,
        "estimate_eur": estimate,
        "award_as_pct_of_estimate": _display(_pct(award, estimate)),
        "award_below_estimate_eur": estimate - award,
        "electronic_tenders_received": tenders,
        "initial_months": initial,
        "maximum_months": maximum,
        "subcontract_reported_pct": reported,
        "subcontract_as_pct_of_award": _display(sub_award),
        "subcontract_as_pct_of_estimate": _display(sub_estimate),
        "reported_pct_matches_estimate_not_award": sub_estimate == reported and sub_award != reported,
        "subcontract_percentage_denominator_verified": False,
        "documented_existing_capabilities": sorted(k for k, v in seen.items() if v == "documented_existing"),
        "awarded_contract_requirements": sorted(k for k, v in seen.items() if v == "awarded_contract_requirement"),
        "prepublication_api_delivery_verified": False,
        "actual_cash_paid_eur": None,
        "qa_only_contract_value_eur": None,
        "renewals_exercised": None,
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue": None,
        "warning": "One selected broad infrastructure award. Neither contract value nor planned features establish paid QA-only demand, delivered capabilities, subcontract opportunity or AgentMine revenue.",
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(analyze(json.loads((root / EVIDENCE).read_text(encoding="utf-8"))), indent=2))
