# Exchange architecture — proposed v0.1

Buyer agent -> gateway -> supplier discovery -> quote and route -> spending policy -> explicit human approval -> authorized payment provider -> supplier -> result validation -> receipt and buyer agent.

Core modules: registry adapter, quote normalization, policy/approval, procurement orchestration, provider adapters, delivery verification, immutable audit trail. Start as a modular monolith. Data objects: request, supplier, offer, approval, purchase, artifact, receipt.

Approval binds one exact price, provider, license and expiration. Deny payment if missing, expired or mismatched. Idempotency prevents duplicate charges. Separate paid-but-not-delivered state from success. Never store card details or expose supplier data as trusted instructions. Use external payment provider; no custody or escrow in MVP.

MVP: simulate purchase with one provider and no money, then sandbox provider; real-money pilot requires explicit owner approval. Marketplace, open auctions and automatic spending mandates are later options.
