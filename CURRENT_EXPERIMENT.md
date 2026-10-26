# Current experiment — data-first agent exchange wedge
Status: in progress, no validated paid demand. Updated 2026-10-08.

## Goal
Rank near-term Agent Exchange opportunities using observable supply, transaction, price, buyer diversity, licensing and implementation effort. Do not block research on interviews. Interviews are optional follow-up, not phase gate.

## New external observations (source pages, not audited ledgers)
- x402scan live dashboard: https://www.x402scan.com/ reported a 30-day rolling snapshot of 4.57M transactions, $968.11K volume, 30.62K buyers, 39K sellers at retrieval. This is a changing snapshot, not a historical fixed dataset; wallet counts are not distinct paying people, and transactions may include spam/self-payments.
- x402scan featured provider sol.blockrun.ai reported 2.15M transactions, $53.89K volume, 163 buyers in that snapshot. Strong concentration / low buyer diversity: investigate repeat authentic customers before interpreting transactions as demand.
- x402scan featured provider claw402.ai describes paid API access without API keys or registration, reported 428.36K transactions, $975.59 volume and 136 buyers. This is a **direct competitor** to procurement access, not an unserved gap. Validate numbers independently.
- Coinbase Bazaar MCP server supports resource search and proxy calls: https://docs.cdp.coinbase.com/api-reference/v2/rest-api/x402-facilitator/bazaar-mcp-server . Generic paid endpoint discovery alone is not differentiated.
- Official MCP Registry read-only API allows paginated discovery and search: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md . MCP listing is supply, not usage or payment.

## Hypotheses to prioritize by data, not narrative
1. Quality-adjusted routing and vendor reliability evidence: differentiation over existing discovery/payment solutions. Find measurable uptime/latency/price and buyer churn signals.
2. License-aware quote comparison / budget policy: likely enterprise pain but no demonstrated willingness to pay.
3. Agent-native RFQ and procurement: plausible but competition (claw402 and Bazaar) means basic pay-per-call is not a moat.
4. Vertical data procurement for a narrow high-value task: compare observed spend and actual buyers.

## Immediate next experiment
Create reproducible public-source collectors with snapshot timestamp, source URL, raw evidence, pagination, deduplication and quality flags. Analyze provider concentration, average value per transaction, buyer diversity and competition. Avoid ungrounded extrapolation. Then choose the cheapest testable integration and build a no-payment quote simulator.

## Stop/pivot conditions
Do not build generic marketplace or payment facilitator if existing providers already satisfy discovery/payment. Avoid prioritizing metrics dominated by a handful of wallets or providers. No live spend, real wallet funding or public monetized deployment without explicit owner approval.

## Weekly execution gate — 2026-10-26
**Status:** Phase 0; no verified paid demand or revenue. Current technical controls are offline and do not demonstrate real supplier savings or delivery economics.
1. **Procurement outcome cohort (predeclared):** 20 consecutive, dated CPV 48/72 public notices; record inclusion criteria, source ID, original notice, accessible submission portal, stage, date, amendments, and missing access. Keep primary and third-party labels separate. Analyze mismatch only for independently verified records, with denominator; do not infer legal error from directory differences.
2. **Supplier preflight comparison:** 3 source-backed example decisions and opt-in paired trials versus current workflow/incumbents. Measure decision correctness, minutes, variable cost and at least 3 explicit price/pilot responses. No private procurement documents without permission. No-response and no-benefit are outcomes.
3. **Agent routing alternative:** 3 real lawful public-information tasks comparing direct versus proposed routing. Only call delivery or savings *observed* with timestamped independently supported outputs and actual variable cost. Synthetic quotes remain scenarios.
4. **Monetization gate:** no transaction fee, Supplier Growth SaaS, Lost Demand Intelligence or opt-in RFQ paid launch until actual identifiable consented buyers, a repeatable outcome and credible unit economics. Published x402 wallet settlements and competitor list prices do not meet this gate.
5. **Licensing:** use Licitera free CC BY 4.0 monthly bulk only with attribution; full history/OData is separately licensed and not authorized for redistribution or competing data API (https://licitera.se/villkor/datamodul, version 2026-10-20).
**Pivot hypothesis:** charge for independently verified exception resolution (e.g. procurement-stage ambiguity cleared from original notice/portal) or opt-in RFQ fulfillment, not raw API listings. Test buyer need and liability boundaries before building.
**Sources:** https://licitera.se/oppen-data ; https://www.kommersannons.se/eLite/Notice/NoticeOverview.aspx?ProcurementId=73494 ; https://licitera.se/upphandling/servicearendehanteringssystem-32fcaba7cd ; https://x402-list.com/api/v1/stats ; GitHub Actions https://github.com/kianaghaei-create/agentmine/actions/runs/40288717963 .
