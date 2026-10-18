# ModelBrain flows

Every flow the product runs, step by step. Each step names the component, the query (from `docs/queries.cypher`) or endpoint (from `docs/API.md`), and what happens on failure. If code behaves differently from this file, the code is wrong.

Conventions
- Hub graph name: `hub`. Tenant graphs: `tenant_kestrel`, `tenant_harbor`. Sandboxes: `sbx_<8 hex>`.
- `now` is milliseconds since epoch (UTC). Ids are prefixed: `rul_`, `fact_`, `evt_`, `task_`, `drf_`, `job_`, `sbx_`.
- "Template text" means the deterministic explanation in `app/engine/explain.py`, used when no LLM key is set or the LLM call fails.

---

## F0. Startup (API process boot)
1. Load config from env (`.env.example` lists all). Missing `HF_TOKEN` -> log a warning, continue anonymously (500 requests per 5 minutes).
2. Connect to FalkorDB (`FALKORDB_HOST/PORT/PASSWORD`). Retry 10 times with 2 s backoff; if still down, start anyway and report `falkordb: "down"` on `/api/health` (the web app shows the maintenance banner).
3. Run the SCHEMA block on `hub` and on each existing tenant graph (index creation is idempotent; ignore "already indexed" errors).
4. **Clause Loader (F3)** runs if the hub has no `Clause` nodes or the last load is older than 7 days.
5. Load `data/roots.json` into memory (org allowlist for `is_root`).
6. **Tenant bootstrap**: if `tenant_kestrel` or `tenant_harbor` does not exist, `GRAPH.DELETE` (ignore missing), then run `data/demo_tenants/<slug>.cypher`, then **seed rulings**: for every Deployment run the verdict flow F1 with the company's context and write a ruling (T1). Record each tenant name in the in-memory tenant registry and in hub node `(:TenantRegistry {name})` (names only, no usage data).
7. **Prewarm** (background task, does not block startup): ingest (F2) every model in `data/prewarm.json` (the demo set plus the 40 eval models), then run the Resolver (F4) once.
8. Start APScheduler jobs: Watcher every `WATCH_INTERVAL_MINUTES` (F9), sandbox cleanup every 15 minutes (F7.5), clause reload daily at 03:00 UTC (F3).
9. Mount the MCP server at `/mcp` (F5). Serve.

## F1. Verdict (web, API, MCP and CI all call this)
Input: `model_id`, `context`, optional `tenant` + `token`, optional `deployment_id`, optional `expected_ruling_id`, `strict` (default false).
1. **Validate**: `model_id` matches `^[A-Za-z0-9][\w.-]{0,95}/[\w.-]{1,96}$`; `context.hq_country` is ISO-2; `markets` is a list of ISO-2 (default `[hq_country]`); `mau` >= 0 (default 0); `commercial` bool (default true); `distributes_weights` bool (default false); `end_user_only` bool (default false). Invalid -> 422 `INVALID_INPUT`.
2. **Freshness check**: read `Model` + ancestors with Q3 (min_tier 0). If the model is missing, or any ancestor node has `ingested_at` older than 6 h, or a referenced parent node has no `ingested_at` (placeholder created by I4): start ingest (F2) for the model. If ingest finishes within 4 s, continue; otherwise return 202 `{status: "QUEUED", job_id}` and the client follows `GET /api/jobs/{id}/events`, then re-calls verdict.
3. **Effective min tier** = 2 if `strict` else 1.
4. **Ancestry**: run Q1 with `model_id`, `min_tier`. Drop null clauses. Build `paths` (one per row), `inherited_licenses` = set of non-null `license` keys excluding the queried model's own row.
5. **Completeness**: run Q2. Lineage is **incomplete** if any returned `top` has `is_root = false`. Collect `incomplete_reasons`: `"<top> declares no parent and is not a known base model"`.
6. **Clause evaluation** (`app/engine/clauses.py`) for every clause on every row:
   - Build the evaluation scope: `context` + `ancestor_multimodal = row.multimodal` + the queried model's own properties for `check`.
   - `applies_when` false -> skip. True -> classify by `effect`.
   - A clause whose `quote` is null after loading counts as `NEEDS_COUNSEL` regardless of its `effect` (F3 rule).
   - For `OBLIGATION` with a `check`: status SATISFIED / NOT_SATISFIED; without `check`: NOT_CHECKABLE.
   - Deduplicate clauses by `id`; keep the shortest path that carried each clause (for display) and the list of all paths (for `explain`).
7. **Decide** (first match wins):
   1. any applicable `BLOCK` -> `BLOCKED`
   2. lineage incomplete, or any licence key on any path is `unknown` or `other`, or any applicable `NEEDS_COUNSEL` -> `CANNOT_DETERMINE`
   3. any applicable `OBLIGATION` -> `ALLOWED_WITH_OBLIGATIONS`
   4. otherwise -> `ALLOWED`
8. **Declared differs**: `declared_differs = true` if the queried model's own licence key differs from any inherited licence key and the inherited licence has at least one clause with effect BLOCK or OBLIGATION. Report `declared_license` and `inherited_licenses`.
9. **Alternatives** (only if BLOCKED): for up to 8 ids from `data/alternatives.json[pipeline_tag]` (fall back to `text-generation`), run steps 4-7 using cached hub data only (no new ingest during a request); include those that are `ALLOWED` or `ALLOWED_WITH_OBLIGATIONS`. Label the section "Alternatives in our candidate set".
10. **Explanation**: build the evidence list; if `OPENROUTER_API_KEY` is set and the daily budget allows, ask the LLM to phrase a 2-4 sentence explanation **using only the evidence JSON** (prompt in `app/engine/explain.py`); on any LLM error or timeout (6 s) use template text. Never let the LLM change the verdict.
11. **Persist (only when `tenant` is given)**:
    1. Authorise: `token` must match the sandbox token or `ADMIN_TOKEN`; fixed tenants are read-only for visitors (403 `READ_ONLY_TENANT`).
    2. If `expected_ruling_id` is given and the deployment's latest ruling (T6 filtered by deployment) is a different id -> 409 `STALE_RULING` with the latest ruling in the body.
    3. Write the ruling and facts with T1. One `Fact` per (path node, licence) actually used. `hub_sha_set` = shas of all nodes on all paths.
    4. If a previous active ruling exists for the deployment, T2 (`SUPERSEDES`) and create `Event {kind: SUPERSEDED}` on the old one.
12. **Respond** with the verdict JSON (`docs/API.md` `Verdict`), including `cypher` (the exact query text for Q1 and Q2) for the "show the Cypher" panel, and the disclaimer.

Failure handling: FalkorDB error -> 503 `GRAPH_UNAVAILABLE`; Hub unavailable and the model is not cached -> 503 `HUB_UNAVAILABLE` with `retry_after_s`; ingest exceeded caps -> verdict still computed on what was ingested, with `incomplete_reasons` including "ingest cap reached".

## F2. Ingest (Scout)
Input: `model_id`, `children` (bool, default false), caps: depth 6, 300 nodes, 25 children per relation per node.
1. Create job `job_<id>` (in-memory registry + SSE channel). Emit `{"type":"started"}`.
2. BFS queue = [model_id]; visited = {}.
3. For each id popped:
   1. `GET /api/models/{id}?blobs=true` via the HF client (F2.6). 404 -> mark `Model {id, missing: true}` and continue. 401/403 (private) -> same with `private: true`.
   2. Parse (`app/hf/parse.py`):
      - `declared_license`: `cardData.license` (string or list: take the first), else the first `license:<x>` tag, else null. Normalise with `clauses.seed.json.normalise` -> key; null -> `unknown`; unmapped -> `other`.
      - Parents: `cardData.base_model` (string or list) plus tags `base_model:<relation>:<id>`; relation from the tag (`finetune`, `adapter`, `merge`, `quantized`); if only `cardData.base_model` is present, relation = `finetune` for a single parent, `merge` for a list.
      - `pipeline_tag`; `multimodal` = pipeline_tag in {image-text-to-text, visual-question-answering, image-to-text, any-to-any, video-text-to-text} or tags contain `multimodal` or `vision`.
      - `is_root` = owner org in `roots.json` and no declared parent.
      - `name_starts_with` = first token of the repo name split on `-`, `_`, `.`.
      - `has_license_file` = any sibling whose filename upper-cased contains `LICENSE` or `LICENCE`.
      - `card_has_llama_notice`: fetch `https://huggingface.co/{id}/raw/{sha}/README.md` (skip on 401/403/404) and search case-insensitively for `Built with Llama`.
      - Fingerprints: every sibling ending `.safetensors` or `.bin` with `lfs.sha256` -> `weights_sha256:<sha256>`; `tokenizer.json` (or `tokenizer.model`) -> `tokenizer_sha:<lfs.sha256 or blobId>`; `config.json` -> fetch raw at `sha` (skip on 401/403), canonical JSON of the keys listed in BLUEPRINT 6.3 sorted, sha256 -> `config_fp:<hex>`.
   3. Write: I1, I2, I3, I5 (each fingerprint), I4 (each parent). Emit `{"type":"node","id":...}`.
   4. Enqueue parents (if depth < 6 and visited < 300).
4. If `children`: for the root model only, `GET /api/models?filter=base_model:<relation>:<id>&limit=25` for each relation; ingest each child without recursion (one level) and write I4 child->root.
5. Emit `{"type":"done","nodes":n}`. Job retained 10 minutes.
6. HF client rules: one shared async limiter (capacity 400 requests per 5 minutes with token, 90 without); 10 s timeout; on 429 sleep `Retry-After` (default 20 s) and retry up to 3 times; on 5xx retry 3 times with 1, 2, 4 s backoff; cache JSON responses on disk keyed by URL for 6 h (README/config keyed by `id@sha`, kept until the sha changes).

## F3. Clause Loader
1. Read `data/clauses.seed.json`.
2. For each licence: MERGE `License {key, name, url}`; for each clause: fetch `source_raw_url` (cache 7 days on disk); normalise text (HTML: drop `<script>`/`<style>`, strip tags, unescape entities; then collapse whitespace); split with `split_regex`; take the first unit matching `locator` (case-insensitive); cap at 80 words + " …". Set `Clause.quote`.
3. If fetch fails or nothing matches: `Clause.quote = null`, log `CLAUSE_UNRESOLVED <id>`. Such clauses are treated as NEEDS_COUNSEL by F1.6.
4. MERGE `Clause {id}` with all fields (`applies_when` and `check` stored as JSON strings), and `(License)-[:IMPOSES]->(Clause)`.
5. Record `(:ClauseLoad {at, resolved, unresolved})` in the hub.

## F4. Resolver (hidden lineage)
Trigger: after prewarm; after any ingest that wrote a model with no declared parent; nightly.
1. R1: `algo.WCC` over `Model` + `Fingerprint` via `HAS_FP`.
2. For each component with more than one model: for each model `m` in it with no outgoing `DERIVED_FROM` and `is_root = false`:
   1. R2 to get candidate roots with `shared_kinds`.
   2. Rule: `weights_sha256` in shared_kinds -> relation `mirror`, conf 0.97, tier 1. Else `tokenizer_sha` and `config_fp` both shared -> relation `inferred`, conf 0.8, tier 1. Else only `config_fp` -> relation `inferred`, conf 0.5, tier 0. Else skip.
   3. Pick the first candidate (R2 ordering). R3 to write the edge with `evidence = "shared " + kinds joined + " with " + root`.
3. Emit a resolver report (counts per rule) to logs and `GET /api/admin/resolver/last`.
4. Run F20 (weight DNA resolver) on the same trigger.

## F20. Weight DNA resolver, fingerprint and crawl
See `docs/ADDENDUM_WEIGHT_DNA.md` for sampling (section 2), graph fields (section 3), merge fit (section 6), GGUF (section 5) and wording (section 1.2).

### F20.1 Sample and write fingerprint
1. `services/api/app/hf/dna.py` (safetensors) and `app/hf/gguf.py` (GGUF-only repos) sample weight values through the HF client (30 s timeout, one retry; CDN range reads with at most 10 in flight).
2. Validate vector length 1024 in Python before W1 (FalkorDB silently accepts wrong-length vectors). Non-OK statuses use W1B and log `{repo, sha, status, reason}` at INFO.
3. Reference bases from `data/dna_references.json` are fingerprinted first (`fingerprint_from` mirror when gated); W1 writes the vector on the **official** node with `dna_reference = true`.

### F20.2 Resolver step (after F4 hash resolver; also G093 nightly)
For each model with `dna_status = 'OK'`, `dna_reference` not true, and no existing `DERIVED_FROM` with `method` in `weights` or `weights_merge`:
1. W2 with `k = 50`, `min_sim = DNA_RELATED_MIN` → up to 5 candidates (same `dna_sig`, older `created_at`; never a `dna_reference` node).
2. **Merge check first:** least-squares fit on stored vectors (addendum section 6); if accepted, W7 and stop.
3. Else W3 on the best W2 row: `tier = 1` if `sim >= DNA_DERIVED_MIN` else `0`, `method = 'weights'`. On an existing declared edge, W3 only sets `weights_sim`.
4. Never overwrite declared edges. Conflicts (declared parent ≠ weights parent, different families) remain both edges; W5 lists them.
5. Extend resolver report at `GET /api/admin/resolver/last` with `dna: {ok, gated, quantized, unsupported, no_safetensors, error, edges_created, edges_corroborated, merges_found, gguf_ok}`.

### F20.3 Vocab DNA and GGUF licence
1. `vocab_dna` fingerprint from `tokenizer.json` or GGUF `tokenizer.ggml.tokens` (addendum 5.3); `HAS_FP` only — shared vocab alone never creates an edge in F4 or F20.
2. GGUF header: W9 sets `format`, `gguf_*` fields; when `general.license` normalises and the card declares none, `DECLARES {source:'gguf_meta'}`.

### F20.4 Crawl
`services/api/app/jobs/dna_crawl.py`: Scout ingest (canonical id), fingerprint, F20.2; resumable via `DnaCrawl` and `dna_at` vs `last_modified`; `POST /api/admin/dna/crawl`, `GET /api/admin/dna/crawl/{job}`. Never commit sampled weight values.

## F5. MCP `can_i_use` (Claude Code, Cursor)
1. Client connects to `https://<api>/mcp` (streamable HTTP). Server lists tools: `can_i_use`, `explain`, `lineage`, `watch`, `confirm_edge` with JSON schemas from `docs/API.md`.
2. `can_i_use(model_id, hq_country, commercial=true, markets?, mau?, strict=false, tenant?, token?)` calls F1. If F1 returns QUEUED, the tool waits up to 20 s polling the job, then re-runs F1; if still queued returns `{verdict:"QUEUED", job_id, hint:"call again in a few seconds"}`.
3. Tool result: a short text block first line `VERDICT: BLOCKED (EU company; Llama 3.2 multimodal licence rights are not granted in the EU)` then the path, then up to 3 clause summaries with source URLs, then `Details: <web url>/m/<id>?hq=DE`, then the disclaimer. Also return the full Verdict JSON as structured content.
4. `explain(model_id | ruling_id)` returns all paths, clauses with quotes, tiers, and "what would change the answer" (list of counterfactuals: HQ outside EU, strict off, a confirmed edge).
5. Rate limit per MCP session: 30 calls per minute.

## F6. Tenant ruling with concurrency control
See F1.11. Additional rules:
1. Rulings are never edited. "Change" = new ruling + `SUPERSEDES` + `Event{SUPERSEDED}`.
2. A UI that shows a ruling sends its id as `expected_ruling_id` on "Re-check"; a 409 shows "Someone updated this deployment a moment ago" with the newer ruling and a "Use the latest" button.

## F7. Sandbox (visitor acts as a company)
1. `POST /api/sandbox {template: "kestrel" | "harbor"}`; rate limit 3 per hour per IP; maximum 50 live sandboxes (oldest deleted first).
2. Name `sbx_<8 hex>`; `GRAPH.COPY tenant_<template> sbx_<id>` (fails if the destination exists: regenerate the id and retry once).
3. Token = 32 random bytes urlsafe; store `{name, token_hash, template, expires_at = now + SANDBOX_TTL_MINUTES}` in memory and in hub `(:Sandbox {name, expires_at})` (no token in the graph).
4. Return `{tenant: "sbx_<id>", token, expires_at}`; the web app keeps the token in sessionStorage and sends it as header `X-Tenant-Token`.
5. Cleanup job: `GRAPH.DELETE` expired sandboxes and their registry entries.

## F8. Confirm edge -> Publisher -> verdict flips (compounding)
1. In tenant A, a person clicks "Confirm this parent" on an inferred edge (`child`, `parent`). `POST /api/tenants/{t}/confirm` with token.
2. API writes `Event {kind: CONFIRMED_EDGE, reason: child + " -> " + parent}` in tenant A, signed by the acting person.
3. Publisher: `tenant_hash = sha256(PUBLISHER_SALT + tenant_name)[:16]`; P1 on the hub. Returns `{tier, confirmations}`.
4. If the tier changed: Watcher-style fan-out limited to that edge: F1 for every active ruling in every tenant whose facts include `child` (T3 with `[child]`), create `Event {kind: REOPENED, reason: "edge confirmed by another organisation"}` + `Task {REVIEW_RULING}` (T4).
5. Demo: Kestrel confirms (1 confirmer, tier stays 1); a second confirmer is needed. For the demo, the second confirmation comes from the Harbor sandbox (or the `ADMIN_TOKEN` "public evidence" button that adds `public:<url>` as a confirmer with the evidence link). Tier becomes 3; Harbor's strict verdict for `shuyuej/Llama-3.2-1B-GPTQ` (or the Sicarius model) changes from CANNOT_DETERMINE to the licence-driven verdict.
6. The hub stores only hashes; the UI shows "confirmed by 2 independent organisations" with no names.

## F9. Watcher -> fan-out -> reopen -> handoff -> approve -> supersede
1. Every `WATCH_INTERVAL_MINUTES`: watched set = all `Deployment.model_id` in all tenants + their ancestors (Q3) + `data/watchlist.json`. Cap 200 per run; rotate.
2. For each id: `GET /api/models/{id}` (cache bypass). If `sha` equals `Model.sha`, skip.
3. Changed: re-run F2 for that id only (no children), which writes a new Snapshot (I2) and updates DECLARES (I3).
4. Diff old vs new: `license_changed`, `license_file_added`, `notice_added`, `parents_changed`. If the new card declares a parent that was previously inferred, D3 query to promote to tier 4.
5. D1 query (descendants) -> affected ids = {id} + descendants.
6. For each tenant (registry): T3 with affected ids -> for each row T4 (reopen + task assigned to owner). Emit fan-out summary `{changed, descendants, tenants: {name: count}}` into `(:FanOut {at, model_id, summary})` in the hub.
7. Auditor agent claims each REVIEW_RULING task (T5), recomputes F1 for the deployment, stores the proposed verdict on the task (`proposed_verdict`, `proposed_ruling_json`), sets `state = AWAITING_APPROVAL`, and hands off: `Task {kind: APPROVE_RULING}` -[:HANDED_OFF_FROM]-> the review task, assigned to the deployment owner.
8. Owner approves in the UI (`POST /api/tasks/{id}/approve`): write the new ruling (T1) + `SUPERSEDES` (T2) + `Event {APPROVED}` signed by the person. Reject: `Event {REJECTED}`; the old ruling stays active with a "reviewed, kept" note.
9. D2 query computes fix leverage for the UI.

## F10. Notifier -> approval -> post -> loop closes
1. Trigger: a verdict on a hub model with `declared_differs = true`, or a Watcher diff where a parent added a notice but descendants did not (fix leverage > 0).
2. Notifier drafts title + body (LLM if available, else template in `app/agents/notifier.py`): neutral, specific, links to the upstream licence, offers the exact card change, signs "Sent with ModelBrain (automated screening, not legal advice)". Stored as `Draft` + `Task {APPROVE_POST}` in the acting tenant (or the admin tenant for hub-level drafts).
3. Approve: if `target_repo` is in `HF_POST_ALLOWLIST` -> post with `HF_WRITE_TOKEN` via the Hub discussions API (`POST https://huggingface.co/api/models/{repo}/discussions` with `{title, description}`; verify the payload during Block 5) -> store `posted_url`. Otherwise -> mark "ready to copy"; the UI shows a copy button and the repo's community link. Never post outside the allowlist.
4. Loop close (our test repo): the author (us) edits the README to declare the upstream licence and base model; "Check now" (`POST /api/watch/check`) runs F9 for that repo; edge promoted to tier 4; dependent rulings reopen; the Discussion gets an `Outcome {FIXED, days}`.

## F11. Xkev replay
1. `GET /api/replay/xkev` builds (and caches in the hub as Snapshots, Discussion, Outcome) the timeline:
   - commits from `GET /api/models/Xkev/Llama-3.2V-11B-cot/commits/main` (fields: `id`, `title`, `message`, `date`, `authors`), notably `dfdcec1f9f` (2025-11-16, model card tags), `7ee73286de` (AIBOM), `213eb383f1` (README update), `e8c2529775` (2025-11-16 04:02 UTC, "Upload LICENSE_llama.txt");
   - discussion 12 "License compatibility" (status closed, opened 2025-07-09) from `GET /api/models/Xkev/Llama-3.2V-11B-cot/discussions` (fields: `num`, `title`, `status`, `createdAt`, `author`, `numComments`);
   - card state per commit from `raw/{commit}/README.md` (licence field, notice presence) and file list;
   - the 9 direct children and their current declared licence, notice and licence-file status.
2. The UI scrubber moves through events; at the fix event, the parent turns "fixed upstream" and each child shows "did not inherit the fix" with fix leverage 9/9.

## F12. CI check (GitHub Action)
1. The Action scans files, builds `{repo, models, context}` and calls `POST /api/ci/check`.
2. API runs F1 per model (no tenant), returns `{pass, results}`; `pass = false` if any BLOCKED, or any CANNOT_DETERMINE when `strict`.
3. The Action writes a Markdown table to the job summary and exits 1 on failure. If the API is unreachable: warn and exit 0 (never block a team's CI because our demo is down), unless `fail_on_unreachable: true`.

## F13. Eval
1. `eval/models.csv` + `eval/labels.json` committed and hashed before rules exist (`eval/labels.sha256`).
2. `python eval/run_eval.py --api <url>` runs F1 (default and strict) for 80 cases, writes `eval/report.json` (accuracy, false ALLOW count, CANNOT_DETERMINE rate, declared_differs precision/recall, per-case rows).
3. `python eval/baseline_card_only.py` computes the declared-licence-only baseline and, if a key is set, the card-only LLM baseline (prompt: model card text only; ask for one of the four verdicts). Writes into the same report.
4. `GET /api/eval` serves `eval/report.json`; the web `/eval` page renders it with the labels hash.

## F14. Deploy
1. Railway: service `falkordb` from image `falkordb/falkordb:latest`, volume at `/var/lib/falkordb/data`, env `REDIS_ARGS="--appendonly yes --requirepass ${FALKORDB_PASSWORD}"`, env `FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000"` (the image default TIMEOUT is 1000 ms; raise it so ingest batches do not time out), private networking only (no public TCP proxy).
2. Railway: service `api` from `services/api/Dockerfile`; env from `.env.example`; health check `/api/health`; one replica (APScheduler jobs must run once).
3. Vercel: project root `apps/web`; env `NEXT_PUBLIC_API_URL`; production branch `main`.
4. After deploy: run the smoke script `scripts/smoke.sh <api> <web>` (health, verdict OPEA DE, verdict OPEA US, lineage, MCP tool list).

## F15. Failure modes (applies everywhere)
| Failure | Behaviour |
|---|---|
| FalkorDB down | `/api/health` shows `falkordb: "down"`; endpoints return 503 `GRAPH_UNAVAILABLE`; web shows a maintenance banner |
| Hub 429 | limiter waits; requests that would exceed 4 s return 202 QUEUED |
| Hub 5xx or timeout | retries; then cached data if present (response flag `stale: true`), else 503 `HUB_UNAVAILABLE` |
| Model not found | 404 `MODEL_NOT_FOUND` with a "check the id" hint |
| Gated or private files | metadata and hashes still used; config/README skipped; `incomplete_reasons` notes it |
| Ingest cap reached | verdict on partial graph, `incomplete_reasons` includes the cap |
| LLM error | template text; never blocks a verdict |
| Clause source unreachable at load | clause quote null -> NEEDS_COUNSEL; warning in logs and `/api/health.clauses_unresolved` |
| Concurrent ruling write | 409 `STALE_RULING` |
| Sandbox expired | 401 `SANDBOX_EXPIRED` with a "create a new sandbox" action |

## F16. Hosted verdict (OpenRouter path)
1. Catalogue sync (startup and every `OPENROUTER_CATALOG_REFRESH_HOURS`, default 12): `GET https://openrouter.ai/api/v1/providers` -> O1 for each `{slug, name, headquarters, datacenters, terms_of_service_url, privacy_policy_url}`. `GET https://openrouter.ai/api/v1/models` -> for each model with `hugging_face_id`: O2. For models in `data/prewarm.json` hosted list and any model a user asks about: `GET /api/v1/models/{id}/endpoints` -> O3 per endpoint (provider slug = first segment of `tag`, `quantization`, `status`, `uptime_last_30m`). No API key is needed for these public endpoints.
2. A verdict request with `hosted_model_id` (OpenRouter id) runs O5 to get the Hugging Face id, ingests it (F2) if needed, and runs F1 with `distributes_weights = false`.
3. Licence nuance: for hosted use, clauses that apply only to distribution are skipped by their `applies_when`; the Llama EU multimodal exclusion has an end-user exemption, so for hosted use F1 returns the clause as NEEDS_COUNSEL with the summary "You call the model through a provider; whether the exemption for end users covers your product needs counsel" unless `end_user_only` is set.
4. Residency: if `context.data_residency` is set (`"EU"` or a list of ISO-2), O4 with the expanded country list returns serving providers in allowed datacenters. No rows -> `residency: {ok: false, proof: "no provider serves this model from an allowed datacenter"}`; rows -> list of providers with headquarters and terms links.
5. Response: the normal `Verdict` plus `hosted: {or_id, providers_ok: [...], residency_ok: bool}`.

## F17. Licence text watch
1. Daily (and on `POST /api/admin/licence-watch/run`): for every distinct `source_raw_url` in the clause table and every provider `tos_url` for providers serving a deployed hosted model, fetch the text through the web fetcher, normalise, sha256.
2. L2 gets the last sha for the URL. Same -> skip. Different or new -> L1 writes a new `LicenseText` version and links the clauses that use this URL.
3. If the sha changed: re-run the Clause Loader (F3) for those clauses; collect `clause_ids`; for each tenant run T8 and then T4 (reopen + task) with reason "the licence text behind clause <id> changed on <date>".
4. With `WEB_FETCHER=firecrawl` or `anakin`, the provider's change-tracking may be used instead of polling; the graph writes are the same.

## F18. Ask the company brain
1. `POST /api/tenants/{t}/ask {question}`; templates in `app/engine/ask.py`, each a parameterised read-only Cypher over the tenant graph (and the hub where needed): who owns deployment X; which deployments use model X; which rulings reopened since date D; which rulings rest on clause C; who signed ruling R; what is blocked for country C; which products have open tasks; what changed upstream this week.
2. Router: if an LLM key is set, the LLM receives the question and the template list (names, descriptions, parameter schemas) and must return `{template, params}` as JSON; validate it against the schemas. Without a key, a keyword router chooses. Invalid choice -> "I can answer these questions: ..." with the list.
3. Run the template with `ro_query`; answer = rows + the Cypher + sources (ruling ids, commit shas, clause source URLs). Record a `Turn`.

## F19. Voice (browser only, cuttable)
1. The Ask box and the verdict page have a mic button using the browser Web Speech API (`SpeechRecognition`); unsupported browsers hide the button.
2. The transcript goes to F18 (or F1 for "can we use <model> in <country>"), and the short answer line is read back with `speechSynthesis`. No audio leaves the browser except the transcript text.
