"""Evidence-safe supply concentration metrics; never infer buyers from listings."""
from collections import Counter
from decimal import Decimal, InvalidOperation

def summarize(records):
    rows = list(records)
    catalog_rows = [r for r in rows if r.get("evidence_type", "catalog") == "catalog"]
    providers = Counter(str(r.get("provider") or "UNKNOWN") for r in catalog_rows)
    total = len(catalog_rows)
    prices = []
    evidence = Counter()
    for row in rows:
        kind = row.get("evidence_type", "catalog")
        if kind not in {"catalog", "observed_transaction", "verified_customer"}:
            raise ValueError("unknown evidence_type")
        evidence[kind] += 1
        if kind == "catalog" and row.get("price_usd") is not None:
            try:
                price = Decimal(str(row["price_usd"]))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("invalid price") from exc
            if not price.is_finite() or price < 0:
                raise ValueError("invalid price")
            prices.append(price)
    prices.sort()
    n = len(prices)
    median = str(prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2) if n else None
    return {
        "catalog_rows": total,
        "distinct_provider_labels": len(providers),
        "largest_provider_share": max(providers.values()) / total if total else None,
        "provider_hhi": sum((v / total) ** 2 for v in providers.values()) if total else None,
        "priced_rows": n,
        "median_listed_price_usd": median,
        "evidence_row_counts": dict(evidence),
        "verified_distinct_paying_customers": None,
        "revenue_usd": None,
    }
