# AgentMine — Project memory (source of truth)

Last reviewed: 2026-10-08

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
