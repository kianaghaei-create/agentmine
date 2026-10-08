# Roadmap

## Phase 0 — Evidence pipeline (current)
- Implement read-only discovery collectors with explicit auth configuration.
- Normalize resource name, endpoint, service, category, price, network, source URL, observed time and usage fields if available.
- Persist raw snapshots separately from clean records.
- Deduplicate by stable endpoint identity; no invented usage data.
- Validate request failures and missing values.

## Phase 1 — Demand validation
- Inventory 50–100 resources and inspect actual observable usage, where available.
- Interview 5–10 potential developer/buyer users.
- Investigate competition, licences, data costs and source reliability.
- Score niches: frequency, monetary value, exclusivity, acquisition cost, distribution, defensibility.

## Phase 2 — Narrow prototype
- Pick one niche and build a source-backed demo API.
- Verify freshness, accuracy, legal reuse and unit economics.
- Charge first pilot customers via conventional billing and/or x402.

## Guardrails
- Do not buy hardware, paid data, cloud services or deploy public paid endpoints without owner approval.
- No financial trading or investment claims from unvalidated signals.
- Never conflate transactions with unique customers.
