# Agent Procurement — human-approved, automated data/API acquisition

Date: 2026-10-08. Status: hypothesis, not validated business.

## User problem
During AI-led builds, agents frequently stall when an external dataset or API requires the human to register, subscribe, pay and manually provision credentials. Desired experience: agent identifies the exact resource and total price (e.g. $10), requests one explicit approval, then handles compliant purchase/provisioning and resumes work.

## Proposed product
A procurement middleware / MCP tool for AI agents:
1. Agent states dataset, license, freshness, quality, budget and purpose.
2. Broker searches suppliers and verifies terms, one-time vs subscription billing, limits, data rights and all-in price.
3. User receives an explicit quote with provider, exact scope, maximum charge, recurring status, refund/cancellation and data-use rights.
4. **No payment or commitment until user approves** the specific transaction.
5. Payment executes via supported authorized provider (x402 where possible, otherwise approved checkout); never collect or store raw card credentials.
6. Broker provisions access securely, tests response, returns time-limited scoped capability to agent and records receipt, spend and cancellation path.
7. If signup/KYC/CAPTCHA/ToS require a human, pause for human completion; never bypass.

## Candidate monetization
- Transaction fee for successful procurement (micropayment economics must be modeled).
- SaaS per agent team / monthly spend / procurement controls.
- Enterprise policy engine, approval workflow and auditable API spend.
- API supplier distribution and onboarding tools.

## Differentiation hypotheses
Cross-provider purchasing, one-click human approval, credential abstraction, budget enforcement, source quality checks, cost optimization, auto-expiry and provenance. Existing payment rails alone do not solve vendor onboarding, licensing or credential provisioning.

## Major risks
- Providers may not permit delegated signup, resale or credential sharing.
- KYC, tax, refunds, chargebacks, subscriptions and data licensing are nontrivial.
- Many APIs require manual onboarding; cannot promise universal one-click procurement.
- Trust and security: payment authorization, least privilege, scoped secrets, fraud, prompt injection, spend limits.
- Need measurable willingness to pay and buyer distribution.

## MVP wedge
Start with **already machine-purchasable, one-off datasets / x402 APIs**, fixed-price under an explicit per-purchase cap. Return a verifiable receipt and data payload without creating external vendor accounts. Test with 5 developers who have recently hit an API paywall. Expand to standard API subscriptions only after proving safe onboarding and cancellation.

## Research plan
- Interview developers/agent builders about last blocked purchase and minutes lost.
- Inventory 20 machine-purchasable providers, pricing, licensing and auth requirements.
- Review x402, AP2 and payment-provider agent-commerce integrations; distinguish standard specification from actual merchant acceptance.
- Prototype dry-run quote → approval → sandbox purchase → data return; no live charges without explicit owner approval.
- Measure completed tasks, setup time saved, fees and repeat use.

## Decision
Add as a **high-priority opportunity hypothesis**; compare to DaaS and Agent Exchange using OPPORTUNITY_SCORING.md. No claim of validated market demand yet.
