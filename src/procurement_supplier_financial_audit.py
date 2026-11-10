"""Historical supplier SaaS evidence; keep accounting, ARR and cash scopes separate."""
import json
from pathlib import Path

SOURCE = "https://get.mercell.com/hubfs/Mercell-Annual-report-2021.pdf"


def _int(row, key, positive=False, signed=False):
    value = row.get(key)
    if type(value) is not int or (positive and value <= 0) or (not signed and value < 0):
        raise ValueError(f"invalid integer: {key}")
    return value


def analyze(snapshot):
    if (not isinstance(snapshot, dict)
            or snapshot.get("evidence_type") != "historical_audited_financials_and_reported_kpis"
            or snapshot.get("issuer") != "Mercell Holding ASA"
            or snapshot.get("source_url") != SOURCE
            or snapshot.get("financial_year") != 2021
            or snapshot.get("financial_unit") != "NOK_thousands"
            or snapshot.get("kpi_arr_unit") != "NOK_millions"):
        raise ValueError("unbound source, period or units")
    s, g, k = (snapshot.get(key) for key in ("supplier_segment", "group", "reported_year_end_kpis"))
    if not all(isinstance(row, dict) for row in (s, g, k)) or set(k) != {"2020", "2021"}:
        raise ValueError("missing scope or KPI years")
    revenue = _int(s, "revenue", positive=True)
    license_revenue = _int(s, "saas_license_revenue")
    other = _int(s, "other_service_revenue")
    personnel = _int(s, "personnel_expense")
    other_expense = _int(s, "other_expense")
    expenses = _int(s, "operating_expense")
    ebitda = _int(s, "ebitda", signed=True)
    sweden = _int(s, "sweden_revenue")
    group_revenue = _int(g, "revenue", positive=True)
    group_ebitda = _int(g, "ebitda", signed=True)
    group_ebit = _int(g, "ebit", signed=True)
    ocf = _int(g, "operating_cash_flow", signed=True)
    dev = _int(g, "software_and_intangible_development_cash_outflow")
    ppe = _int(g, "property_plant_equipment_cash_outflow")
    if (license_revenue + other != revenue or personnel + other_expense != expenses
            or revenue - expenses != ebitda or sweden > revenue or revenue > group_revenue):
        raise ValueError("financial scopes do not reconcile")
    if not all(isinstance(row, dict) for row in k.values()):
        raise ValueError("invalid KPI rows")
    arr0, arr1 = (_int(k[y], "supplier_arr", positive=True) for y in ("2020", "2021"))
    n0, n1 = (_int(k[y], "supplier_customers", positive=True) for y in ("2020", "2021"))
    proxy0, proxy1 = arr0 * 1_000_000 / n0, arr1 * 1_000_000 / n1
    return {
        "financial_year": 2021,
        "supplier_license_share_pct": 100 * license_revenue / revenue,
        "supplier_segment_share_of_group_revenue_pct": 100 * revenue / group_revenue,
        "sweden_share_of_supplier_revenue_pct": 100 * sweden / revenue,
        "supplier_segment_ebitda_margin_pct": 100 * ebitda / revenue,
        "group_ebitda_margin_pct": 100 * group_ebitda / group_revenue,
        "group_ebit_margin_pct": 100 * group_ebit / group_revenue,
        "group_operating_cash_less_development_and_ppe_nok_thousands": ocf - dev - ppe,
        "reported_supplier_arr_change_pct": 100 * (arr1 / arr0 - 1),
        "reported_supplier_customer_count_change_pct": 100 * (n1 / n0 - 1),
        "year_end_arr_per_reported_supplier_proxy_nok": {"2020": proxy0, "2021": proxy1},
        "year_end_arr_per_reported_supplier_proxy_change_pct": 100 * (proxy1 / proxy0 - 1),
        "supplier_segment_cash_flow": None,
        "supplier_cohort_retention": None,
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue": None,
        "warning": "Historical financials and management KPIs; not current pricing, cash receipts, retention, market share, or AgentMine unit economics.",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.input.read_text())), indent=2))
