# Phase 0 supplier paired-task protocol (consent-only, not yet executed)

**Status (2026-11-02):** Prepared protocol, **zero** recruited suppliers, real paired tasks, price responses, verified savings, or AgentMine revenue. This document is an execution checklist, not evidence of demand. Issue: [#2](https://github.com/kianaghaei-create/agentmine/issues/2).

## Authorization and privacy gate — before any contact or task

1. Obtain owner approval **before outreach**, any use of customer material, spending, payments, or deployment. Do not solicit confidential bids or credentials. Obtain explicit, revocable participant consent for a specific task and for any separate use of aggregated findings.
2. Keep identity, consent proof, source documents and any potentially sensitive details **outside this public repository** in an access-controlled location approved by the owner. Do not store raw queries, private procurement text, company names, contact details, customer IDs, or bid prices in GitHub. Use opaque IDs `T001`, `T002`, etc.
3. Use only lawful publicly accessible original notices, amendments and submission-portal views, or separately authorized sources. If an original/portal/amendment is unavailable, mark source verification incomplete; never bypass access controls or infer an operative deadline from a third-party directory.
4. Predeclare the eligible supplier-task population, observation window and selection order before examining outcomes. Log invitations, opt-outs, nonresponses, excluded tasks and reasons in a private, non-identifying tally; do not silently replace poor outcomes. The fixed 20-notice TED research cohort is **not** a substitute for five real supplier tasks.

## Paired comparison (minimum five genuine tasks)

For each consented supplier decision about a real public IT/software tender (prefer CPV 48/72), have the participant use the **same decision question and information cutoff** with (A) their normal incumbent workflow and (B) the AgentMine preflight. Alternate A/B order across participants/tasks when feasible and record order privately to detect learning bias. Record *actual* start/stop minutes for each method, not retrospective guesses. Avoid presenting historical example cards as real decisions.

A reviewer independent of the two task executions checks the **operative stage, original notice, accessible amendments and portal status** from primary sources at the decision cutoff. Separately record whether the baseline and AgentMine outputs were correct. Mark `primary_source_checked=false` when the independent check is incomplete; an unreviewed or ambiguous case is **not** a correct, verified outcome. Record any wrong stage, deadline or recommendation as an adverse result, including if AgentMine was faster.

Record the actual incremental variable cost per AgentMine task in SEK (e.g., paid requests, inference, external data or manual handling); zero is permitted only when truly zero and supported by a cost ledger. Track review/operator minutes and acquisition/support time **separately**; do not assume these disappear in a scalable product. No paid calls are authorized by this protocol.

## Machine-readable evaluation (existing code, no new module)

Create a **local** JSON snapshot with exactly these fields (values below are an illustrative schema example, **not** pilot data):

```json
{
  "evidence_type": "paired_supplier_preflight_pilot",
  "sample_kind": "synthetic",
  "observed_at_utc": "2026-10-24T18:00:00Z",
  "tasks": [
    {
      "task_id": "T001",
      "consent_recorded": true,
      "baseline_minutes": "45",
      "agent_minutes": "15",
      "baseline_correct": true,
      "agent_correct": true,
      "primary_source_checked": true,
      "incremental_variable_cost_sek": "2"
    }
  ]
}
```

Only for **actual consented observations**, change `sample_kind` to `self_reported_consented` and use genuine measured values. Never relabel synthetic examples. Run offline:

```sh
python -m src.supplier_preflight_pilot --input /private/path/paired_tasks.json --hourly-cost-sek 600 --value-capture-pct 25 --min-tasks 5
```

The hourly rate and capture percentage are **scenario inputs**, not customer prices. The evaluator's quality/economic screens use self-reported fields and **never certify independent verification, price acceptance, customers or revenue**. Retain the private source-check audit and cost evidence outside GitHub; only publish privacy-safe aggregates if consent and non-identification are assured.

## Price/pilot responses (separate from task economics)

After the task, request an **explicit** answer to a concrete proposed pilot/price (e.g. yes, no, conditional, or no response), and the proposed terms. Obtain **at least three explicit responses** from real prospective buyers; record refusals and nonresponses in the denominator. Do not equate a hypothetical labor-value ceiling, an x402 wallet, a directory listing, or an interviewer's positive comment with willingness to pay. Do not take payment or initiate a paid pilot without owner approval.

## Predeclared decision rule

- **Continue narrow validation** only with >=5 consented paired real tasks, primary-source checked outcomes, no unaddressed correctness regression, positive measured net benefit after actual variable costs, and >=3 explicit pilot/price responses showing credible demand. Review rights, acquisition, liability, manual support and repeat usage separately.
- **Stop or narrow** if AgentMine is wrong, sources cannot be independently checked, the time advantage disappears after verification, costs exceed benefit, or buyers decline pricing. Negative and zero-savings observations remain in the denominator.
- **Do not promote Phase 0** from this protocol or from synthetic unit tests. A later commercial decision requires independently supported outcomes and owner approval.

**Current tally (2026-11-02):** 0/5 consented paired tasks; 0/3 explicit price/pilot responses; 0 measured savings; 0 verified AgentMine revenue. No outreach, customer data collection, spend, payment or deployment performed.
