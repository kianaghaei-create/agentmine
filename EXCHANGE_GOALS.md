# Agent Exchange — measurable milestones

Status: proposed milestones, no claims of completed validation.

## G0 — Evidence and architecture (week 1–2 target)
- Publish architecture, flows, boundaries and risk register.
- Inventory >=15 providers with documented price, terms and purchasing method, plus >=5 direct competitors.
- Interview >=5 builders about last paywalled task, actual lost time, frequency and willingness to pay.
- Gate: choose one narrow purchase type supported by real supplier terms; no spend.

## G1 — Dry-run procurement (weeks 3–4 target)
- Agent submits a task; platform returns >=2 attributable comparable offers where available.
- Human sees one-off/recurring flag, exact total, scope, license, expiry; can approve or reject.
- Mocked execution returns receipt and schema-validated test artifact.
- Tests: unauthorized payment impossible, replay/idempotency, timeout, expired quote, malformed supplier response.
- Gate: 3 external users complete workflow; track whether they would pay. No actual payments.

## G2 — Authorized real supplier pilot (weeks 5–8 target, dependent on G0/G1)
- Integrate one legitimate machine-purchasable provider in sandbox.
- Explicit owner approval required before any real spend or public deployment.
- Measure cost per successful transaction, failures, gross margin, manual intervention, time saved.
- Gate: >=1 paid customer/commitment and repeated need, not just demo enthusiasm.

## G3 — Multi-provider brokerage
- >=3 suppliers in one vertical; deterministic routing baseline vs alternatives.
- Reliable receipts, policy controls and vendor failure recovery.
- Gate: repeat purchases, margin after fees, defensible distribution channel.

## G4 — Exchange optional
- Introduce supplier onboarding, reputation, disputes and marketplace fees only after buyer/supplier liquidity evidenced.

## Decision cadence
Weekly go/pivot/stop with opportunity and evidence scored separately. Dates are planning targets, not delivery promises.
