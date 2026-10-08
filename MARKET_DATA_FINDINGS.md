# Market signals — initial scan 2026-10-08

## Evidence and caveats
Source: https://www.x402scan.com/ (rolling 30-day dashboard snapshot retrieved during research).
Reported: 4.57 million transactions, $968,110 volume, 30,620 buyer addresses, 39,000 seller addresses. Snapshot changes continuously and may include bot traffic, self-dealing, test activity and address reuse; numbers are not audited.

Featured:
- sol.blockrun.ai: 2.15 million transactions, $53,890 volume, 163 buyers. Approx $0.025 per transaction; volume/transactions are from provider dashboard, not verified independently.
- claw402.ai: 428,360 transactions, $975.59 volume, 136 buyers. Approx $0.00228 per transaction. It advertises API access without keys or registration, a direct competitor to a generic procurement wrapper.

Coinbase Bazaar MCP already provides resource search and paid endpoint proxy calls: https://docs.cdp.coinbase.com/api-reference/v2/rest-api/x402-facilitator/bazaar-mcp-server .
Official MCP Registry provides paginated public supply discovery: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md .

## Interpretation
High call volume with limited distinct addresses is not proof of broad demand. Generic catalog and payment wrappers are already supplied. Low nominal transaction value means a simple percentage fee may yield weak economics. Investigate quality-adjusted routing, spending policies, procurement receipts and verified delivery instead.

## Next steps
Run read-only registry collector, then get a reliable provider-level transaction export with dated provenance and evaluate buyer concentration, spend, price per successful task and competing suppliers. Do not use snapshots with different crawl dates as a time series. No live payments without explicit owner approval.
