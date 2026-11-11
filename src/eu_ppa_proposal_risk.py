"""Offline planning screen for the reviewed EU Public Procurement Act proposal.

Not a current-law assessment, legal opinion, market forecast or launch approval.
"""
import json
from datetime import date
from pathlib import Path

EVIDENCE = "data/evidence/eu_public_procurement_act_proposal_2026-11-11.json"
SOURCE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52026PC0590"
STATUS = "https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2026%2F0265%28COD%29"
RULES = {
    "network_platform_definition": ("5(6)-(7)", "buyer_supplier_communication_via_interoperability_network"),
    "free_procurement_detail_years_after_award": ("97(1)-(4)", 3),
    "network_communication_access_fee_prohibited": ("131(5)", True),
    "eea_ownership_control_and_storage": ("131(4)", True),
    "supplier_only_nppds_connection_exception": ("131(7)", True),
    "commission_platform_open_source": ("132(1)-(3)", True),
    "electronic_eligibility_service": ("28(1)-(3), 133(1)-(6)", True),
    "contract_reporting_threshold_eur": ("134(4)", 10000),
    "contract_reporting_days": ("134(4)", 20),
    "national_to_eu_transfer_days": ("135(2)", 10),
    "nonpublic_data_access_restricted": ("134(8), 135(3)-(4)", True),
    "application_lag_years": ("149", 2),
}
FEES = {"none", "separate_analytics", "network_communication_access", "procurement_detail_access", "private_transaction_fee"}
DATA = {"none", "existing_public", "future_contract_reporting", "nonpublic_ppds"}


def audit(snapshot):
    """Bind the dated proposal and indicative budget without promoting either."""
    if not isinstance(snapshot, dict) or snapshot.get("evidence_type") != "reviewed_eu_legislative_proposal_not_enacted":
        raise ValueError("expected reviewed proposal evidence")
    p = snapshot.get("proposal")
    if not isinstance(p, dict) or (p.get("celex"), p.get("procedure"), p.get("source_url"),
            p.get("status_url"), p.get("status"), p.get("published_on")) != (
            "52026PC0590", "2026/0265(COD)", SOURCE, STATUS,
            "preparatory_phase_in_parliament", "2026-09-09"):
        raise ValueError("unbound or changed proposal status; review new evidence")
    if any(k not in p or p[k] is not None for k in ("entry_into_force", "application_date")):
        raise ValueError("proposal has no verified effective date")
    try:
        observed = date.fromisoformat(snapshot["observed_on"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid observation date") from exc
    if observed.isoformat() != snapshot["observed_on"] or observed < date(2026, 9, 9):
        raise ValueError("invalid proposal chronology")
    b = snapshot.get("budget")
    if not isinstance(b, dict) or b.get("period") != [2028, 2034] or b.get("basis") != "indicative_legislative_financial_statement_not_appropriated_or_awarded":
        raise ValueError("invalid budget basis")
    values = [b.get(k) for k in ("operational_eur", "human_resources_eur", "total_eur")]
    if any(type(v) is not int or v <= 0 for v in values) or values != [142115000, 21322000, 163437000] or sum(values[:2]) != values[2]:
        raise ValueError("invalid reviewed budget amounts")
    rows = snapshot.get("provisions")
    if not isinstance(rows, dict) or set(rows) != set(RULES):
        raise ValueError("incomplete or changed provisions")
    for key, (article, value) in RULES.items():
        row = rows[key]
        if not isinstance(row, dict) or row.get("article") != article or type(row.get("value")) is not type(value) or row["value"] != value:
            raise ValueError("unbound or changed provision: " + key)
    return {
        "proposal_status": p["status"], "observed_on": snapshot["observed_on"],
        "source_url": SOURCE, "status_url": STATUS, "application_date": None,
        "indicative_budget_eur": values[2], "budget_is_approved_spend": False,
        "current_law_assessed": False, "legal_clearance": False,
        "verified_agentmine_customers": None, "verified_agentmine_revenue": None,
    }


def screen(snapshot, *, network_platform, supplier_only, fee_basis, data_basis):
    """Flag proposed-rule exposure for a hypothetical product, never clear it."""
    base = audit(snapshot)
    if type(network_platform) is not bool or type(supplier_only) is not bool:
        raise ValueError("explicit boolean scope required")
    if not isinstance(fee_basis, str) or fee_basis not in FEES or not isinstance(data_basis, str) or data_basis not in DATA:
        raise ValueError("unknown fee or data basis")
    if network_platform:
        scope = "proposal_platform_definition_indicated"
        connection = "proposed_supplier_only_connection_exception" if supplier_only else "proposed_nppds_connection_required"
        duties = ["standards_and_network", "eea_ownership_control_storage", "eligibility_integration", "free_network_communication_access"]
    else:
        scope = "proposal_platform_definition_not_demonstrated"
        connection = "scope_not_established"
        duties = []
    if fee_basis in {"network_communication_access", "procurement_detail_access"}:
        fee = "proposed_access_fee_conflict" if network_platform else "review_scope_and_access_fee"
    elif fee_basis in {"separate_analytics", "private_transaction_fee"}:
        fee = "not_the_express_access_fee_ban_no_clearance"
    else:
        fee = "no_fee_proposed_in_scenario"
    if data_basis == "nonpublic_ppds":
        access = "restricted_requires_designation_and_authorized_access"
    elif data_basis == "future_contract_reporting":
        access = "proposed_reporting_not_public_availability_or_reuse"
    elif data_basis == "existing_public":
        access = "existing_source_rights_review_separate"
    else:
        access = "no_data_dependency_in_scenario"
    return {**base, "scope": scope, "nppds_connection": connection,
            "other_proposed_platform_duties": duties, "fee_screen": fee,
            "data_access_screen": access, "launch_authorized": False}


def main():
    root = Path(__file__).resolve().parents[1]
    snapshot = json.loads((root / EVIDENCE).read_text(encoding="utf-8"))
    scenarios = {
        "offline_supplier_analytics": (False, True, "separate_analytics", "existing_public"),
        "public_procurement_network_access_fee": (True, True, "network_communication_access", "existing_public"),
        "lost_demand_from_nonpublic_ppds": (False, True, "separate_analytics", "nonpublic_ppds"),
        "future_contract_reporting_analytics": (False, True, "separate_analytics", "future_contract_reporting"),
        "private_agent_exchange_transaction_fee": (False, False, "private_transaction_fee", "none"),
    }
    print(json.dumps({name: screen(snapshot, network_platform=values[0], supplier_only=values[1],
                                    fee_basis=values[2], data_basis=values[3])
                      for name, values in scenarios.items()}, indent=2))


if __name__ == "__main__":
    main()
