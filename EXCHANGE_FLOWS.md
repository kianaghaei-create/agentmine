# Agent Exchange — flows, integration contracts and failure paths

## F1: Quote and human-approved purchase
```mermaid
sequenceDiagram
 participant A as Buyer Agent
 participant E as Exchange
 participant S as Supplier
 participant H as Human
 participant P as Payment provider
 A->>E: Request(task, constraints, max budget)
 E->>S: Fetch capability, quote and terms
 S-->>E: Signed or attributable offer
 E-->>H: Specific price, scope, license, recurring flag
 alt Approval
 H->>E: Approve immutable quote
 E->>P: Authorized payment (idempotency key)
 P-->>E: Confirm or fail
 E->>S: Fulfill paid request
 S-->>E: Data/result + provenance
 E->>E: Validate delivery
 E-->>A: Artifact + receipt + validation report
 else Reject or expire
 E-->>A: No purchase; alternative options
 end
```

## F2: No suitable supplier
Return structured unavailable response with unmet constraints, closest compliant alternatives and optional request-for-quote queue; do not invent suppliers or prices.

## F3: Payment succeeded but fulfillment failed
Persist payment reference; prevent duplicate charges; retry safely, escalate to refund/dispute path when supported; do not mark task delivered.

## F4: Agent-to-agent delegated purchasing (later)
Human grants scoped policy with merchant category, time window, per-order and aggregate budget; agent routes within policy; audit/revoke. Requires robust identity and payment authorization; not MVP.

## API boundary proposal
- POST /requests -> task_id
- GET /requests/{id}/offers -> offer list with source, all-in price, validity
- POST /requests/{id}/approvals -> exact offer hash and human decision
- POST /requests/{id}/execute -> idempotency key; only after authorization
- GET /purchases/{id} -> state, receipt and delivery metadata
- GET /artifacts/{id} -> authorized result or scoped URL

All interfaces illustrative, not live endpoints. Human approval cannot be spoofed by the requesting agent. Purchase authorization must be enforced server-side.

## Observability
Track quote coverage, quote accuracy, conversion, successful fulfillment, median time saved, quality failure, disputes, payment fees, gross margin, repeat purchasers. Avoid fabricated transaction volume.
