# Current experiment — data-first agent exchange wedge
Status: Phase 0, no validated paid demand. Weekly review updated 2026-11-02.

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

## Weekly commercial gate — 2026-11-02 (supersedes older near-term priority text)
**Decision:** Continue narrow supplier exception-resolution validation; pause new generic exchange/catalog, generic preflight, paid search-demand intelligence and generic marketplace engineering. No phase promotion. Source and issue: https://github.com/kianaghaei-create/agentmine/issues/2 .

### Measured evidence vs assumptions
- Fixed predeclared TED cohort: **17/20** independently inspected official originals and **3/20** independently corroborated public portal stage/date views. **0** complete amendment histories, **0** verified operative/legal deadline errors. GitHub Actions' 2026-11-02 public TED XML attempt returned **0/20 parsed** (not 20 new failures of the historical cohort): https://github.com/kianaghaei-create/agentmine/actions/runs/41374195968 .
- **0** AgentMine paying customers, revenue, consented paired supplier outcomes, observed minutes saved, measured variable cost, explicit pilot/price responses or demonstrated retention. Three historical source-linked cards are not actual bid/no-bid supplier decisions. Supplier demand and margin remain UNKNOWN.
- Latest independently documented exact-tree CI: **993/993** tests passed on the 2026-11-02 demand provenance change: https://github.com/kianaghaei-create/agentmine/actions/runs/41402314650 . Subsequent TED coverage guard and four regressions were committed (code c0c3382; tests d5daaa2), but exact-tree CI for that change was not verified at review time. CI tests do not demonstrate buyer value.
- Fresh public publisher snapshot, retrieved 2026-11-02: https://x402-list.com/api/v1/stats reports **1,200 listed services**, **13 delivery-verified**, and **$326,934.95** deduplicated measured listed-service 30-day settlements; **95.4%** of that slice is in the top ten, with largest service imported and its largest buyer accounting for **98.6%** of its flow. The settlement `as_of` remains **2026-10-28T11:42:52Z** despite a 2026-11-02 catalogue refresh. Wallets, catalogues and rolling flows are not verified unique paying businesses or current-period growth.
- Fresh public publisher snapshot, retrieved 2026-11-02: https://nohumans.directory/v1/stats self-reports **100 cumulative purchases / $41.26**: **91 supplier-funded purchases / $37.75** (87 listing fees, 4 verification plans) and **9 buyer-side purchases / $3.51** (2 verdict, 6 demand clusters, 1 demand report). These are a competitor's unaudited cumulative claims, not AgentMine revenue, repeat buyers or positive margin. Operator-funded probes must not be counted as buyer demand.
- Fee-only illustration, NOT a forecast: 4.6% of the x402 List monitored $326,934.95 = **$15,039.01** outside the top ten; 5% capture of that tail at 5% take rate = **$37.60 gross per rolling 30 days before costs**, if all assumptions held. Do not use this slice as ecosystem TAM or assume fees are collectible.
- Supplier ROI hurdle, NOT WTP: a hypothetical **SEK 599/month** product, 5 decisions/month, SEK 600/hour labor value and 25% capture would need **47.92 minutes saved per decision** to cover its price, before incremental costs and quality risk. The inputs are scenarios; no supplier has confirmed them. The public supplier survey supports process friction, not payment intent: https://www.upphandlingsmyndigheten.se/statistik/nationella-upphandlingsenkaten/nationella-upphandlingsenkaten-riktad-mot-leverantorer/en-mangfald-av-leverantorer-och-en-valfungerande-konkurrens-2025/ .

### Next falsifiable test, without spending or unsolicited outreach
1. Reuse `src/supplier_preflight_pilot.py` and existing source-backed cases to prepare a **consent-only, anonymized paired-task protocol**. Do not collect private tender documents or identities in GitHub.
2. On authorization/consent, compare at least **5** genuine supplier tasks against the current workflow/incumbent: independent source-correctness, minutes, actual incremental variable cost, and at least **3 explicit price/pilot responses**. No-response counts as no evidence; synthetic cases never pass.
3. Only after positive outcome and price evidence, test a small paid exception-resolution or provenance-correction pilot (owner approval required). Stop/narrow if supplier time benefit is negligible, correctness regresses, source rights cannot be cleared or price responses are nonpositive.
4. Alternative low-cost pivots to *test*, not build now: (a) B2B source-correction/provenance feed for existing procurement software, sold per independently resolved discrepancy, and (b) supplier-paid verification/exception-resolution service with verifiable deliverables. Both face incumbent competition and uncertain liability, acquisition costs and WTP.
