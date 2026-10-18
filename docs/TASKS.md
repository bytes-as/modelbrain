# ModelBrain task board

This is the hour-by-hour summary. The complete, numbered work list with acceptance tests is `docs/GOALS.md`; Cursor works from GOALS.md and ticks both.

H0 = the moment the build starts. A = backend and graph. B = frontend, eval, video. Tick boxes as you go. Do not start a later block while an earlier block's acceptance criteria fail.

## Block 0 (H0-H1): scaffold and deploy "hello"
- [x] A: create the repo layout from BLUEPRINT.md section 13; `docker compose up` starts FalkorDB + API locally. Done 18 Oct 2026.
- [ ] A: Railway project with two services: `falkordb` (image `falkordb/falkordb:latest`, volume mounted at `/var/lib/falkordb/data` (verify the image's data path), `appendonly yes`) and `api` (Dockerfile in `services/api`). Private networking between them.
- [ ] A: `GET /api/health` returns `{falkordb:"up"}` on the Railway URL. Run the schema block of `docs/queries.cypher` on startup (idempotent).
- [ ] B: Vercel project for `apps/web`; env `NEXT_PUBLIC_API_URL`; home page renders and calls `/api/health`.
- [ ] A: verify and note results here: FastMCP streamable HTTP mount; `GRAPH.COPY`; zero-length paths `*0..6`; constraint syntax.
- **Accept:** both URLs live; health green from the deployed web app.

## Block 1 (H1-H4): ingest and lineage
- [ ] A: `app/hf/client.py` (httpx async, limiter, token, cache, retries), `app/hf/parse.py` (licence normalisation via `data/clauses.seed.json` `normalise`; base_model from `cardData.base_model` and `base_model:<relation>:<id>` tags; multimodal from `pipeline_tag` in image-text-to-text, visual-question-answering, image-to-text, any-to-any; `name_starts_with`; `card_has_llama_notice` by searching README for "Built with Llama"; `has_license_file` from siblings names containing LICENSE).
- [ ] A: Scout ingest: BFS upward to depth 6 / 300 nodes using I1-I4; children fetch for the demo set only.
- [ ] A: load `data/roots.json` (sets `is_root`) and `data/clauses.seed.json` into the hub.
- [ ] A: `GET /api/models/{id}/lineage` using Q3.
- [ ] B: write `eval/models.csv` (40 models, BLUEPRINT section 12), then **label** `eval/labels.json` for both contexts by reading licences and cards. Commit `eval/labels.sha256` before A writes clause logic.
- **Accept:** lineage for `OPEA/Llama-3.2V-11B-cot-int4-sym-inc` returns OPEA -> Xkev -> meta-llama/Llama-3.2-11B-Vision-Instruct; `grimjim/llama-3-Nephilim-v1-8B` returns a multi-parent DAG.

## Block 2 (H4-H8): verdict (the core; protect it forever)
- [ ] A: Clause Loader (FLOWS F3): fetch each `source_raw_url`, extract the quote with `locator` and `split_regex`, store on `Clause.quote`; 33 of 34 locators were verified on 18 Oct; unresolved -> NEEDS_COUNSEL.
- [ ] A: `app/engine/clauses.py` rule evaluator + checks; `app/engine/verdict.py` (BLUEPRINT 6.2); explanation template; disclaimer.
- [ ] A: `POST /api/verdict` (no tenant), golden tests: OPEA in DE commercial = BLOCKED with the EU clause; OPEA in US = ALLOWED_WITH_OBLIGATIONS; `Qwen/Qwen2.5-7B-Instruct` in DE = ALLOWED_WITH_OBLIGATIONS or ALLOWED; a cc-by-nc model commercial = BLOCKED; a parentless re-upload in strict mode = CANNOT_DETERMINE.
- [ ] B: home page (input, example chips, context controls), verdict page (badge, declared vs inherited strip, path graph, clause cards with quotes and links, obligations checklist, disclaimer, collapsible Cypher).
- [ ] Prewarm the demo set on API start (background task).
- **Accept (H8 milestone):** on the public URL a stranger can paste the OPEA id and see BLOCKED for DE and amber for US, with the path and a verbatim quote, in under 5 s for a cached model.

## Block 3 (H8-H12): tenants, memory, MCP
- [ ] A: seed `tenant_kestrel` and `tenant_harbor` from `data/demo_tenants/*.cypher` (fictional, labelled), one active ruling per deployment (T1).
- [ ] A: `/api/verdict` with tenant writes a ruling (T1/T2), honours `expected_ruling_id` (409 when stale).
- [ ] A: sandbox: `POST /api/sandbox` copies a tenant template into `sbx_<id>` (GRAPH.COPY or replay seed), token, 2 h TTL, cleanup job.
- [ ] A: tasks: claim/approve/reject (T5), events, `Person-[:SIGNED]->Event`.
- [ ] A: MCP server at `/mcp` with `can_i_use`, `explain`, `lineage`, `watch`, `confirm_edge` (BLUEPRINT section 8).
- [ ] B: `/tenants` side-by-side page; `/mcp` page with the `claude mcp add` command; record a clip of Claude Code calling `can_i_use`.
- **Accept:** from Claude Code, `can_i_use` on OPEA for DE returns BLOCKED with the path; the Kestrel tenant shows a new ruling.

## Block 4 (H12-H16): resolver and compounding
- [ ] A: fingerprints (I5) for every ingested model; config fingerprint per BLUEPRINT 6.3.
- [ ] A: R1 WCC, R2 candidates, R3 inferred edges with tiers and evidence; strict mode wiring.
- [ ] A: Publisher (P1) + `POST /api/tenants/{t}/confirm`; salted hash with `PUBLISHER_SALT`.
- [ ] B: `eval/run_eval.py` (calls the API for all 80 cases), `eval/baseline_card_only.py` (declared-licence rules + card-only LLM), `/eval` page.
- **Accept:** `SicariusSicariiStuff/Llama-3.2-1B_Base_FP8` shows an inferred edge to `meta-llama/Llama-3.2-1B` with evidence; strict verdict is CANNOT_DETERMINE; after Kestrel and a second confirmer confirm, Harbor's strict verdict changes; false ALLOW count is 0 on the eval.

## Block 5 (H16-H19): watcher, fan-out, loop
- [ ] A: Watcher job (APScheduler, every 10 min) over watched models; "check now" endpoint; Snapshot (I2); diff; D1 descendants; T3/T4 reopen + tasks; D2 fix leverage.
- [ ] A: Xkev replay endpoint from real commits and discussion 12 (cache the fetched history in the hub as Snapshot and Discussion/Outcome nodes).
- [ ] A: live loop on our own test repo (README + config only): Notifier draft -> Approve -> post discussion (allowlist) -> edit card -> check now -> tier 4 + reopened rulings.
- [ ] B: `/replay/xkev` timeline and fan-out visual; `/live-loop` page.
- **Accept:** all three demo shots in BLUEPRINT section 1 run end to end on the deployed site.

## Block 6 (H19-H21): hardening
- [ ] Rate limits (slowapi) and global HF limiter; ingest caps; LLM budget; error and empty states; mobile layout check.
- [ ] GitHub Action + demo repo PRs (red and green).
- [ ] Tests green in CI; a Playwright smoke test for home -> verdict.
- **Accept:** a cold visitor on a phone can run a verdict; a judge's own model id works or shows a clear queued/unknown state.

## Block 7 (H21-H23): submission assets
- [ ] README: what it is, live URL, video, MCP command, setup (local + deploy), graph data model (BLUEPRINT 5.1-5.3), the queries (link `docs/queries.cypher`, explain Q1, Q2, R1, D1, P1, T3, A1-A4), algorithms used, tracks (T1 primary; T2, T3), eval and labels hash, AI coding assistant disclosure, limitations and wording disclaimer.
- [ ] Video (3 min) per BLUEPRINT section 15. Upload, link in README.
- [ ] Blog post draft for the side prize.
- **Accept:** the submission checklist in BLUEPRINT section 17 is fully ticked.

## Block 8 (H23-H24): buffer and submit
- [ ] Submit with all tracks named. Re-check the live URL from a private window.

## Verification log (fill in)
- FastMCP mount: verified with mcp 1.30.0 (pin `mcp>=1.10,<2`); see BLUEPRINT section 3.
- GRAPH.COPY: works on falkordb/falkordb:latest (18 Oct); destination must not exist.
- `*0..6` zero-length paths: work (18 Oct).
- algo.WCC config map + YIELD node, componentId: works (18 Oct).
- Constraint syntax: not needed; MERGE on indexed ids is idempotent.
- HF commits endpoint fields: `{id, title, message, date, authors}` (verified 18 Oct). Discussions: `{num, title, status, createdAt, author, ...}`.

## What the owner needs to bring (18 Oct 2026)

The build can continue without these. They block a public demo, gated model files, paid baselines, and the live posting loop.

- **Hugging Face read token** (`HF_TOKEN`). Free, from https://huggingface.co/settings/tokens with read scope. Needed for Hub rate limits and for README/config on gated Meta repos. Anonymous access still works for public metadata, with a lower limit.
- **Railway, on your own account.** The CLI on this machine is logged in as mani7833 (`mnkreddy7833@gmail.com`), not this repo's owner. Do not deploy ModelBrain there. Log in as yourself (`railway login`), then say so. Expect about $5–15 for an always-on API plus FalkorDB with a volume through judging. A card is required.
- **Vercel** (Hobby is enough) for `apps/web`. The Vercel CLI is not installed here. Log in and say so. `NEXT_PUBLIC_API_URL` must be the Railway API URL.
- **OpenRouter** (`OPENROUTER_API_KEY` plus `LLM_MODEL`, an exact id from https://openrouter.ai/api/v1/models). Optional. Explanations, drafts, and the card-only eval baseline use templates when this is empty. A few dollars of credit covers the demo. `EVAL_BASELINE_MODELS` is only for the multi-model baseline, which is cuttable.
- **Hugging Face write token** (`HF_WRITE_TOKEN`) and a test repo you own, containing only a README and a config, no weights. Put that repo id in `HF_POST_ALLOWLIST`. Only the live posting loop needs this, and that loop is cuttable.
- **Firecrawl or Anakin keys.** Not needed. The default fetcher is plain HTTP, which is enough for the clause quotes.
- **Eval labels.** `eval/labels.json` must be written by a person, 80 verdicts, and committed before the clause engine (G033). Do not leave this until the end.
- **Later, a person, not a vendor:** Claude Code screen recording, the 3-minute video, and the submission form before 23:00 IST.

## Questions for the owner
- This machine already runs Homebrew Redis on port 6379, so `docker compose up` cannot publish FalkorDB on host port 6379. A local untracked `docker-compose.override.yml` publishes host port 6380 instead. The API container still uses `falkordb:6379` on the compose network, and the Browser stays on `localhost:3000`. Should the committed compose file keep 6379 (clean machines) and leave the override local?
- BLUEPRINT section 16.5 and G115 suggest MIT. On 18 Oct 2026 the owner asked for free use with a royalty if someone commercialises the project. No OSI licence can require a royalty, so the repo uses PolyForm Noncommercial 1.0.0 plus `COMMERCIAL.md` for a separate royalty-bearing commercial licence. G115 is not ticked as MIT.
