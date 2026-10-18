# Judge-day runbook

Everything here works with the local stack (`docker compose up`) and with a deployment. Set two shell variables first and never paste the token anywhere public:

```bash
API=http://localhost:8000          # or the deployed API URL
ADMIN=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)
```

## Is it healthy?

```bash
scripts/smoke.sh "$API" http://localhost:3001
```

Exit code 0 means: FalkorDB up, OPEA is BLOCKED in DE and not in US, lineage reaches Meta, the Xkev replay sees 9 descendants, weight fingerprints exist, MCP lists `can_i_use` and `trace_weights`, and the main pages return 200.

`GET /api/health` shows `hf: "degraded"` for five minutes after any Hugging Face failure (rate limit, 5xx, network). Verdicts for models already in the graph keep working; new models wait.

## First start on a fresh FalkorDB (about 30 minutes, mostly unattended)

1. Start the stack. Startup applies the schema and vector index, seeds the fictional tenants (Kestrel, Harbor), marks the 36 foundation references and prewarms the demo models.
2. Fingerprint the references and the demo findings. Needs `HF_TOKEN` for a reasonable rate (400 requests per 5 minutes; anonymous is 90):
   ```bash
   curl -s -X POST "$API/api/admin/dna/crawl" -H "Authorization: Bearer $ADMIN" \
     -H 'content-type: application/json' -d '{"include_scout_findings":true}'
   curl -s "$API/api/admin/dna/crawl" -H "Authorization: Bearer $ADMIN"   # repeat until "state":"done"
   ```
   About 285 models in 25 minutes. The crawl ends by running the hash resolver and the weight resolver.
3. Add the two verified merges and the wrong-base demo:
   ```bash
   curl -s -X POST "$API/api/admin/dna/crawl" -H "Authorization: Bearer $ADMIN" -H 'content-type: application/json' \
     -d '{"include_scout_findings":false,"model_ids":["pravdin/Qwen2.5-0.5B-linear-merge","152334H/miqu-1-70b-sf","ShinojiResearch/Senku-70B-Full","paloalma/ECE-TW3-JRGL-V1","microsoft/UserLM-8b","qingy2024/GRMR-V3-L1B"]}'
   ```
4. Reset the compounding demo (Harbor has confirmed the Sicarius edge; the next visitor's confirmation lifts it to tier 3):
   ```bash
   curl -s -X POST "$API/api/admin/demo/compounding" -H "Authorization: Bearer $ADMIN"
   ```
5. Run the smoke test.

## Before recording the video or before judging

- Reset the compounding demo (step 4 above). After one visitor confirms, the edge stays at tier 3 for everyone until it is reset.
- Open `/findings`, `/replay/xkev`, `/hidden-lineage` once so the Hub responses are cached.

## Restart

- Local: `docker compose restart api`. FalkorDB keeps its data (append-only file on the volume). Visitor sandboxes survive the restart: their token hashes are stored on `Sandbox` nodes in the hub.
- A crawl that was running stops with the API. Start it again: models already fingerprinted are skipped.

## Re-seed tenants (never the hub)

Deleting a tenant graph and restarting the API re-creates it from `data/demo_tenants/*.cypher`:

```bash
docker compose exec falkordb redis-cli GRAPH.DELETE tenant_kestrel
docker compose exec falkordb redis-cli GRAPH.DELETE tenant_harbor
docker compose restart api
```

With a password set, add `-a "$FALKORDB_PASSWORD"` to `redis-cli` (not on a shared screen).

## Re-run the weight resolver after changing thresholds

```bash
curl -s -X POST "$API/api/admin/dna/reset-edges" -H "Authorization: Bearer $ADMIN"   # removes inferred weight edges only
curl -s -X POST "$API/api/admin/dna/resolve" -H "Authorization: Bearer $ADMIN"
```

Declared edges are never touched.

## Hugging Face rate-limits us

- Symptoms: `hf: "degraded"`, `HUB_UNAVAILABLE` (503 with `retry_after_s`) for models not yet in the graph.
- Everything already ingested keeps answering from FalkorDB.
- Wait for `retry_after_s`, or set `HF_TOKEN` and restart the API.

## Rotate tokens

Change `ADMIN_TOKEN` (and `FALKORDB_PASSWORD` if set) in `.env` or the platform's variables and restart the API. Changing `PUBLISHER_SALT` changes every confirmer hash, so existing confirmations stop matching new ones: do it only with a fresh hub, then reset the compounding demo.

## Sandboxes

Visitor sandboxes (`sbx_*`) are copies of a fictional tenant, live two hours, are capped at 50, and are cleaned every 10 minutes. A sandbox graph with no registry entry is deleted on the next cleanup.
