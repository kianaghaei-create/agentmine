# AgentMine — Project memory (source of truth)

Last reviewed: 2026-10-12

## North star
**Build a profitable, scalable, low-touch business that can earn money in the background.** DaaS / x402 / agent APIs are hypotheses, **not** the goal. Pivot freely when evidence supports a better opportunity. Prefer recurring revenue, high gross margin, repeatable distribution, low operating overhead, legal data access, and a defensible advantage.

## Founder preferences
- Entrepreneurial curiosity, unusual opportunities and experiments encouraged.
- Prioritize money earned and customer value, not vanity metrics or a fashionable stack.
- No significant spending or infrastructure purchases before validation and explicit approval.
- Make assumptions explicit; measure and kill weak ideas quickly.
- Automation is an enabler, not a guarantee of passive income. Monitor operations and support costs.

## Current thesis
Agents and their builders need fresh, reliable, machine-readable data. Some may pay per call via x402 or conventional subscriptions. The initial experiment is a market radar that inventories data APIs and tests for real, recurring demand. This thesis is provisional.

## Current state
- Repo initialized with README, ROADMAP, RESEARCH_BACKLOG, read-only x402 collector and initial unit tests.
- Issue #1 tracks collector and demand research.
- **No verified live dataset, paying customers, revenue or product-market fit yet.**
- Coinbase discovery may require authentication. Do not invent metrics or mistake catalog listings for actual paying demand.
- Repository was public at last check; never commit secrets or sensitive customer data.

## Decision log
| Date | Decision | Rationale | Revisit when |
|---|---|---|---|
| 2026-10-08 | Begin with agent market research, not NAS purchase | Reduce capital risk and test demand | Evidence of buyers and infrastructure needs |
| 2026-10-08 | Allow pivots beyond DaaS/x402 | Profitability and defensibility are the true goals | Every weekly review |
| 2026-10-08 | GitHub is durable project memory | Preserve continuity across chats and agents | Every meaningful change |

## Next actions
1. Confirm authorized x402 discovery access and test collector against real responses.
2. Expand evidence sources: MCP registries, API marketplaces, GitHub usage and buyer pain.
3. Identify and rank three monetizable niches, with evidence strength and data licensing.
4. Interview prospective buyers; test willingness to pay and acquisition channels.
5. Consider unconventional adjacent opportunities (data quality guarantees, change alerts, workflow outcomes, intelligence about agent spend) only with validated economics.

## Update protocol
- Read PROJECT_MEMORY.md, NORTH_STAR.md, ROADMAP.md, CURRENT_EXPERIMENT.md and latest issue before acting.
- After material work, update project state, findings, blockers, decisions and next steps.
- Every week review hypotheses and pivot triggers; do not rewrite history: append to DECISION_LOG.md.
- Record unknowns explicitly. Link source evidence and dated results.
- A scheduled reminder can prompt a review, but **does not by itself guarantee GitHub writes**; confirm commits.

## Verified implementation update — 2026-10-08
- Added `intelligence.py` (commit `1946ff5`) and `test_intelligence.py` (commit `2ccdc03`) to main. Measures provider concentration (top-provider share and HHI), listed median price and evidence row categories; intentionally reports paying-customer identities and revenue as unknown.
- Seven local tests of equivalent functionality passed before publishing. GitHub-hosted CI execution of the committed version has not been confirmed.
- No live market dataset or verified paid demand added. Next: run repository tests on exact committed code, integrate real provenance-preserving collector output and compute dated concentration snapshots. No spending or deployment.

## Intelligence data integrity correction — 2026-10-08
- Found mixed-evidence counting defect: transaction observations inflated catalog supply, supplier HHI and listed price distribution.
- Fixed in `intelligence.py` commit `0c295fc`; added regression coverage in `test_intelligence.py` commit `f0f98dc`.
- Previous seven tests passed locally on prior version; updated eight-test suite / GitHub CI not yet independently executed. No new verified market demand, customers, revenue or live data.
- Next: execute updated tests and connect timestamped source-backed catalog snapshots before interpreting concentration or pricing.

## Verified engineering progress — 2026-10-09
- Added eight regression cases to `tests/test_exchange_intelligence.py` (commit `9c73e6f`) covering strict booleans, nonnegative integer budgets, currencies, suppression threshold and explicit unverified-demand labeling. The equivalent 13-test suite passed locally before publication; committed-version CI has not been verified.
- Added read-only, source-attributed `src/x402stats_evidence.py` (commit `4fdd97f`). It preserves raw text and parsed snapshots separately, checks weekly headline consistency and publication-versus-observation lag, and never equates wallet counts with verified customers. Equivalent local fixture suite passed 12/12 tests. Publication of the accompanying regression-test file was denied by safety controls; it is NOT in the repository.
- External source check: x402stats `https://x402stats.io/llms-full.txt` updated 2026-10-09T05:15:14.695Z, but its latest weekly headline observation is dated 2026-10-05. Figures are publisher estimates, not independent transaction/customer verification. Do not treat the 2026-10-08 daily outlier as a proven demand collapse.
- The Exchange Intelligence module already existed in `src/exchange_intelligence.py`; no duplicate module was created. No verified buyers, payment conversion, revenue, or paid willingness to pay.
- Next: publish x402stats regression tests when permitted, run the exact committed suite, validate source parsing against a saved real response, and compare supply against independently evidenced demand. No costs, customer data, or public deployment.

## Registry pagination integrity — 2026-10-09
- Published `src/collect_mcp_registry.py` commit `b2dfac0`. `collect_snapshot` now reports `complete`, `next_cursor`, and `pages_fetched`, so capped registry crawls cannot be silently presented as full-market censuses. It also detects repeated cursors on the final allowed page. Previous `collect` and `collect_with_provenance` interfaces remain available.
- Equivalent local collector implementation passed 8/8 unit tests, including 6 new pagination/compatibility cases; committed-version CI has not run (no GitHub Actions runs available). Attempt to publish new test cases was blocked by safety controls; tests are **not committed**. Do not bypass this restriction.
- No live registry census, independently verified paying demand, supplier revenues, or new transaction evidence was established in this run. Next: publish regression tests only through permitted means; then run a dated read-only full/partial registry snapshot and distinguish listings from unique active providers.


## Registry supply metrics — 2026-10-09
- Published `src/registry_supply_metrics.py` commit `7d8123b` and `tests/test_registry_supply_metrics.py` commit `55e29a2`. The offline analyzer consumes the existing collector JSON snapshot, separates listing rows from unique server names, counts publisher namespace labels, reports coverage and sample HHI, and suppresses full-registry HHI for incomplete crawls.
- Eight equivalent local unit tests passed before publication. The published code and test files were independently read back from GitHub; no GitHub Actions runs exist, and the exact committed test suite has not been executed in CI.
- The official MCP Registry documentation confirms `version=latest` and cursor pagination. Its public unfiltered API returned multiple versions of the same server on 2026-10-09; therefore version and server identity must not be conflated. Source: https://registry.modelcontextprotocol.io/v0.1/servers .
- No full live crawl, independently verified supplier businesses, paying customers, demand or revenue. The container runtime could not resolve the registry host, so a reproducible dated census remains pending. A complete registry crawl would still not represent the entire agent market.
- Next: execute the committed tests in an authorized environment, run the collector with `--max-pages` large enough to report completeness, then analyze its saved JSON via `python -m src.registry_supply_metrics --input <snapshot.json>`. Compare repeat snapshots before proposing supplier growth alerts or RFQ monetization. No spending or deployment.

## Verified state reconciliation — 2026-10-12
- `src/rfq_demand_evidence.py` is present on main (previously reported commit `e81b553`, confirmed by reading the current file). It performs offline opt-in RFQ aggregation, canonical request-ID deduplication, separate synthetic/self-declared cohorts, and token-concentration suppression. Consent and buyer identity are **self-declared**, not independently verified. No live demand or revenue is established.
- Re-ran the 21-case RFQ regression suite locally against the previously prepared source snapshot on 2026-10-12: 21/21 passed. This is **not** GitHub CI or a test of the exact committed source blob. Attempt to publish `tests/test_rfq_demand_evidence.py` was explicitly blocked by safety checks; the test file remains uncommitted. Do not circumvent the block.
- Rechecked publisher x402stats source (updated 2026-10-12T10:02:25Z): 94 heuristic-qualified seller wallets out of 39,123 seller wallets with any revenue (~0.240%), organic 30-day volume $684,900 of raw $1,056,293. These are publisher-reported wallet/flow estimates, **not** unique companies, AgentMine customers, or independently validated sales. Source: https://x402stats.io/llms-full.txt ; methodology: https://x402stats.io/methodology .
- Reconciliation caveat: summing the publisher's 30 listed UTC daily raw volume values for 2026-09-13 through 2026-10-12 gives $1,049,669.84, which is $6,623.02 (~0.627%) below the $1,056,292.86 rolling 30-day headline. This is a **window/boundary reconciliation question**, not evidence of falsification or an API failure; do not equate UTC-day sums with a rolling window without timestamps.
- EU TED official Search API is documented as anonymous/read-only POST `/v3/notices/search`, suitable for future direct evidence gathering; **no live TED query or customer payment signal was obtained in this run**. Source: https://docs.ted.europa.eu/api/latest/search.html .
- Next: publish RFQ regression tests only if security permits; measure a real, timestamped buyer/supplier dataset and conversion/cost signals before prioritizing transaction fees, Supplier Growth SaaS or opt-in RFQ. No spending, deployment or sensitive customer data.

## Independent x402 market coverage check — 2026-10-13
- Published source-attributed `data/evidence/x402_list_stats_2026-10-13.json` (commit `a790b19`, read back from GitHub). Source: https://x402-list.com/api/v1/stats ; publisher-computed 2026-10-12T23:06:28Z; license CC BY 4.0. Publisher reports 942 listed services, 7,018 endpoints, 707 services with measured traction, 12 delivery-verified services, 881 payment-ready services. These are directory/verification categories, **not** AgentMine customers.
- In its own measured listed-service slice (not all x402), publisher reports $413,191.66 deduplicated 30d settlements, 11,037 distinct buyer addresses, 96.9% of volume among top 10 services, and 64% in the top service; that top service's flow is imported and its largest buyer accounts for 99%. These are **publisher claims, not independently audited sales**. Their 32.8% coverage is of their measured facilitator flow, not ecosystem coverage. Address counts do not establish distinct people or businesses.
- Competitor capability check: https://x402-list.com/api advertises free read API, monitoring, price/risk/buyer analytics, a $0.25 x402 on-demand assessment and $0.01 requests beyond the free daily API quota. These are published offerings, **not verified paid conversions**. Generic discovery/quality routing is therefore already competitively supplied; test a narrow workflow outcome and buyer willingness to pay before building another directory.
- Local TED terminal-page fix passed 6/6 focused regression tests but a standard GitHub update to `src/ted_notice_evidence.py` was explicitly blocked by safety checks. Do not bypass; published TED source remains unchanged. No live TED demand, AgentMine revenue, payments, or deployment.
- Next: use timestamped free-source snapshots to distinguish supplier listings, observed wallet settlements and actual prospective buyer needs; evaluate narrow opt-in RFQ / Supplier Growth pilots only with genuine consent and buyer evidence. No paid requests or public deployment.

## 2026-10-15 06:42 Europe/Stockholm — read-only validation; publishing blocked
- Re-read NORTH_STAR, ROADMAP, CURRENT_EXPERIMENT, issue #1 and source. Confirmed exchange intelligence already exists in `src/exchange_intelligence.py` and catalog `intelligence.py`; do not duplicate.
- Re-ran offline x402 List timestamp-fix bundle (previously prepared) with 16/16 local tests passing, including four new timestamp CLI regressions. This is not CI and is not a run against committed patched code.
- Ordinary `update_file` for `src/x402_list_evidence.py` was denied by safety controls; no code commit. Do not bypass or misstate status. Historical `--input` still incorrectly stamps processing time as fetch time on main.
- Official Upphandlingsmyndigheten 2025 advertising statistics (published 2026-06-01) show 18,015 advertised tenders and SEK 982bn estimated advertised value; 2024 figures were 17,575 and SEK 931bn, mean 4.6 bids. Official 2025 procurement development report says median 3, mode 2 and almost one in five tenders received only one bid (2024 reference). These indicate a competition problem, not buyer demand for AgentMine or verified sales. Sources: https://www.upphandlingsmyndigheten.se/statistik/upphandlingsstatistik/statistik-om-annonserade-upphandlingar-2025/ ; https://www.upphandlingsmyndigheten.se/statistik/upphandlingsstatistik/statistik-om-annonserade-upphandlingar-2024/ ; https://www.upphandlingsmyndigheten.se/globalassets/dokument/publikationer/rapport-om-utvecklingen-pa-upphandlingsomradet-2025.pdf
- Attempt to create dated structured tender evidence file was also denied by safety controls. No commit, spend, sensitive data or public deployment. Next: reattempt only ordinary permitted writes when safety allows; prioritize actual CPV-level bid-count observations and opt-in buyer validation over generic directories.


## 2026-10-19 — Official supplier barriers (published; analysis code blocked)
- Source: Upphandlingsmyndigheten, national supplier survey 2025, published 2026-03-13: https://dkn-pslot.upphandlingsmyndigheten.se/statistik/nationella-upphandlingsenkaten/nationella-upphandlingsenkaten-riktad-mot-leverantorer/en-mangfald-av-leverantorer-och-en-valfungerande-konkurrens-2025/ . Invited 20,000, answered 1,912 (9.56%); deliberate prior-bidder oversampling and multiple-answer questions. Cohort-specific denominators not supplied on page.
- Published exact source-backed former-bidder versus never-bidder nonparticipation barrier percentages in `data/evidence/supplier_barriers_2025_official.json` (commit dd75496). Former bidders: complexity 36.4%, unclear requirements 24.2%, time cost 17.7%, future tender visibility 14.8%; never bidders: 14.4%, 4.7%, 6.5%, 9.4% respectively. These are survey responses among non-bidders in past 24 months, not all suppliers, buyer demand, or payment intent.
- Locally tested an offline descriptive comparison module (10/10 tests), but GitHub rejected the standard code-file publication by safety checks. No code or tests from this experiment are on main. Do not bypass restrictions or claim committed CI.
- Strategic implication: prior bidders who stopped participating report larger complexity and requirement-friction percentages than never-bidders. A narrow CPV-48 evidence-linked bid/no-bid preflight is worth validating against actual time saved and buyer willingness to pay; this survey alone does not establish product-market fit. Continue existing Phase 0 decision gates, with no spend or deployment.
