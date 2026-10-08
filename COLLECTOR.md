# Collector usage

Requirements: Python 3.10+; standard library only.

```bash
export CDP_BEARER_TOKEN="YOUR_AUTHORIZED_TOKEN"
python -m src.collect_x402 --max-items 100
python -m unittest discover -s tests -v
```

The Coinbase discovery endpoint documents bearer authorization. If you lack credentials, the collector exits with an error and **does not create fake observations**. Do not commit tokens or raw proprietary responses.

Outputs: timestamped raw JSON pages and normalized CSV under `data/output/`. The CSV preserves atomic payment amounts (do not assume a token's decimals), source and collection timestamp. Missing utilization metrics stay blank. Catalog listings do not prove paid usage.

To try a different facilitator's authorized discovery endpoint, pass `--url`. Confirm terms, pagination and authentication before using.

## Next research steps
- Verify live endpoint access and paginate to 100 unique resources.
- Check returned metrics against source semantics.
- Add category labeling, duplicate MCP tool handling and pricing normalization.
- Interview prospective buyers; do not treat API listings as validated demand.
