# Deploy on Railway (one project, three services)

Everything runs on Railway: FalkorDB needs a long-running process with a volume, and the API and web app sit next to it on private networking. Budget about 45 minutes the first time. Do not put the database on a free tier that pauses or deletes idle instances.

Set a spend limit on the Railway project before anything else (G114).

## 1. FalkorDB (private only)

- New service from image `falkordb/falkordb:latest`.
- Volume mounted at `/var/lib/falkordb/data`.
- Variables (generate the password, never paste it in chat or commit it):
  - `FALKORDB_PASSWORD` = a long random string
  - `REDIS_ARGS` = `--appendonly yes --requirepass ${{FALKORDB_PASSWORD}}`
  - `FALKORDB_ARGS` = `MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000` (the image default TIMEOUT is 1000 ms, too short for the algorithms)
- No public domain. The image runs with protected mode off, so it must only be reachable on the private network.
- If the API later cannot connect over private networking, add `--bind 0.0.0.0 ::` to `REDIS_ARGS` (some environments resolve private hosts over IPv6).

## 2. API

- New service from this GitHub repo. Root directory: repository root. Builder: Dockerfile at `services/api/Dockerfile`. One replica (rate limits and sandbox registry are in-process).
- Variables:
  - `FALKORDB_HOST` = `${{FalkorDB.RAILWAY_PRIVATE_DOMAIN}}` (use the service's actual name)
  - `FALKORDB_PORT` = `6379`
  - `FALKORDB_PASSWORD` = `${{FalkorDB.FALKORDB_PASSWORD}}`
  - `ADMIN_TOKEN`, `PUBLISHER_SALT` = long random strings (new ones, not the local values)
  - `HF_TOKEN` = a read-only Hugging Face token (optional, raises the Hub rate limit from 90 to 400 requests per 5 minutes)
  - `CORS_ORIGINS` = the web service's public URL, e.g. `https://modelbrain-web.up.railway.app`
  - `NEXT_PUBLIC_API_URL` = this API's own public URL (used for links in MCP answers)
- Generate a public domain. Health check path: `/api/health`.
- The container listens on `$PORT` (set by Railway).

## 3. Web

- New service from the same repo. Root directory: `apps/web`. Build: `npm ci && npm run build`. Start: `npm run start` (Next.js reads `$PORT`).
- Variable `NEXT_PUBLIC_API_URL` = the API's public URL. It is baked in at build time: redeploy the web service after changing it.
- Generate a public domain, then put it in the API's `CORS_ORIGINS` and redeploy the API.

## 4. Seed the data (seconds, from the local hub)

1. Locally: `make reset` (clean fictional tenants), then `make export` (writes `exports/`, git-ignored).
2. On the FalkorDB service, enable a temporary TCP proxy in Railway's networking settings. Note its host and port.
3. Locally: `FALKORDB_PASSWORD=<the Railway password> make import FALKOR_HOST=<proxy host> FALKOR_PORT=<proxy port>`. Every graph must print `ok`.
4. Remove the TCP proxy again.
5. Restart the API (startup re-applies indexes, marks the 36 foundation references and seeds anything missing).
6. Reset the compounding demo: `curl -s -X POST https://<api>/api/admin/demo/compounding -H "Authorization: Bearer <ADMIN_TOKEN>"`.

Without an export, run the crawl from `docs/RUNBOOK.md` instead (about 25 minutes with `HF_TOKEN`).

## 5. Verify

```bash
ADMIN_TOKEN=<prod admin token> scripts/smoke.sh https://<api> https://<web>
```

All checks must say `ok`. Then open `https://<web>` in a private window and click through `/`, `/findings`, `/hidden-lineage`, `/replay/xkev` and `/companies`.

Point MCP clients at `https://<api>/mcp`, and the GitHub Action's `api_url` at `https://<api>`.

## Rollback

Redeploy the previous successful deployment from Railway's deployments list. Data lives on the FalkorDB volume and is untouched by API or web redeploys. A full data restore is `make import ... --replace` from the last export.
