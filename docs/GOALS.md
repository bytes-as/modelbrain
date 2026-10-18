# ModelBrain goals (the definition of done)

138 goals, in build order. Work top to bottom. A goal is done only when its **Accept** condition is true and its **Verify** step has been run; tick it and write the date. If a goal must be cut, strike it through and write the reason; only goals marked *(cuttable)* may be cut, in the order of BLUEPRINT.md section 14. References: FLOWS = `docs/FLOWS.md`, API = `docs/API.md`, UI = `docs/UI.md`, Q = `docs/queries.cypher`.

Milestones: **M1** = G001-G019 (O1), **M2** = G020-G029 (O4), **M3 (core, never break)** = G030-G049 (H8), **M4** = G060-G079 (H12), **M5** = G050-G059 (H16), **M6** = G080-G099 (H19), **M7** = G100-G114 (H21), **M8** = G115-G125 (H23), **Add-ons** = G126-G138 (after M6, G126 in Block 2).

---

## 1. Foundation (M1)
- [x] **G001** Repo created during the event with the layout in BLUEPRINT section 13; first commit message `chore: scaffold ModelBrain`. **Accept:** tree matches section 13. **Verify:** `git log --reverse | head -3` shows a 18 Oct 2026 first commit. Done 18 Oct 2026.
- [x] **G002** `docker compose up` starts FalkorDB (`falkordb/falkordb:latest`, data at `/var/lib/falkordb/data`, `REDIS_ARGS=--appendonly yes`, `FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000"`) and the API. **Accept:** `curl localhost:8000/api/health` returns `falkordb:"up"`; FalkorDB Browser loads on `localhost:3000`. **Verify:** run both commands. Done 18 Oct 2026.
- [x] **G003** `services/api/pyproject.toml` pins: fastapi, uvicorn, pydantic>=2, httpx, falkordb, apscheduler, slowapi, `mcp>=1.10,<2`, pytest (the OpenRouter client is plain httpx; no LLM SDK needed), pytest-asyncio. **Accept:** `pip install -e .` succeeds in a clean Python 3.12 container. **Verify:** `docker build services/api`. Done 18 Oct 2026.
- [x] **G004** `app/config.py` reads every variable in `.env.example` with types and defaults; missing `HF_TOKEN` logs a warning, missing `ADMIN_TOKEN` or `PUBLISHER_SALT` fails startup. **Accept:** unit test for config. **Verify:** `pytest tests/test_config.py`. Done 18 Oct 2026.
- [x] **G005** Structured JSON logging with request id middleware (`X-Request-Id`), no secrets logged. **Accept:** every response carries `X-Request-Id`; a log line contains it. **Verify:** curl any endpoint, grep logs. Done 18 Oct 2026.
- [x] **G006** Error envelope and codes exactly as API "Conventions"; global exception handler maps exceptions to codes. **Accept:** unit tests for 404, 422, 503 envelopes. **Verify:** `pytest tests/test_errors.py`. Done 18 Oct 2026.
- [x] **G007** CORS allows only `CORS_ORIGINS`. **Accept:** a request from another origin is rejected. **Verify:** curl with `Origin: https://evil.example`. Done 18 Oct 2026.
- [x] **G008** `apps/web` Next.js app (App Router, TypeScript, Tailwind) with the global layout, nav and footer from UI "Global layout"; health dot calls `/api/health`. **Accept:** page renders at 375 px and 1280 px. **Verify:** Playwright screenshot at both widths. Done 18 Oct 2026.
- [x] **G009** CI workflow (GitHub Actions) runs API tests against a FalkorDB service container and builds the web app on every push. **Accept:** green run on main. **Verify:** Actions tab. Done 18 Oct 2026.
- [x] **G010** `app/graph/db.py`: FalkorDB connection with retry (10 tries, 2 s), `query()` and `ro_query()` helpers taking parameters, graph selection by name, and a `GRAPH.COPY` helper. **Accept:** unit tests against the service container. **Verify:** `pytest tests/test_db.py`. Done 18 Oct 2026.
- [x] **G011** `app/graph/queries.py` contains every query from Q verbatim as named constants (SCHEMA, I1-I5, Q1-Q3, R1-R3, D1-D3, P1, T1-T8, A1-A5, O1-O5, L1-L2). **Accept:** a test asserts each constant equals the corresponding block in `docs/queries.cypher` (whitespace-normalised). **Verify:** `pytest tests/test_queries_in_sync.py`. Done 18 Oct 2026.
- [x] **G012** Schema bootstrap runs SCHEMA on `hub` and tenant graphs at startup, idempotently. **Accept:** restarting the API twice produces no errors. **Verify:** restart and check logs. Done 18 Oct 2026.
- [x] **G013** No string-built Cypher with user input anywhere. **Accept:** a test greps `services/api/app` for f-strings or `+` concatenation inside `.query(` calls and finds none. **Verify:** `pytest tests/test_no_cypher_injection.py`. Done 18 Oct 2026.
- [x] **G014** All variable-length patterns are bounded (`*0..6` or `*1..6`). **Accept:** a test greps queries.py for `*]` or `*)` without bounds and finds none. **Verify:** same test file. Done 18 Oct 2026.
- [ ] **G015** Railway services `falkordb` (private networking, volume, `requirepass`) and `api` are deployed; Vercel project for `apps/web`. **Accept:** public `/api/health` green from the Vercel page. **Verify:** open the Vercel URL.
- [ ] **G016** `scripts/smoke.sh <api> <web>` checks health, verdict for OPEA in DE and US, lineage, and MCP `tools/list`. **Accept:** exits 0 against the deployment. **Verify:** run it.

- [x] **G017** `.env.example` is complete and matches `app/config.py` exactly (a test compares the variable lists). **Verify:** `pytest tests/test_env_example.py`. Done 18 Oct 2026.
- [ ] **G018** `Makefile` targets: `up`, `down`, `test`, `smoke`, `eval`, `seed`, `reset` (deletes and re-seeds tenant graphs only, never the hub). **Verify:** run each target.
- [x] **G019** Lint and format: ruff + black for Python, eslint + prettier for web, run in CI. **Verify:** CI green. Done 18 Oct 2026.

## 2. Hugging Face ingest (M2)
- [x] **G020** `app/hf/client.py`: async httpx, shared limiter (400/5 min with token, 90 without), 10 s timeout, retries per FLOWS F2.6, disk cache (6 h JSON; README/config keyed by `id@sha`). **Accept:** unit tests with a mock server for 429 and 5xx. **Verify:** `pytest tests/test_hf_client.py`. Done 18 Oct 2026.
- [x] **G021** `app/hf/parse.py` implements every parsing rule in FLOWS F2.3.2 (licence, parents and relation, pipeline tag, multimodal, is_root, name_starts_with, has_license_file, card_has_llama_notice, fingerprints). **Accept:** unit tests with recorded fixtures of 6 real models (OPEA, Xkev, meta-llama/Llama-3.2-11B-Vision-Instruct, SicariusSicariiStuff/Llama-3.2-1B_Base_FP8, grimjim/llama-3-Nephilim-v1-8B, Qwen/Qwen2.5-7B-Instruct). **Verify:** `pytest tests/test_parse.py`. Done 18 Oct 2026.
- [x] **G022** Licence normalisation uses `clauses.seed.json.normalise`; null -> `unknown`; unmapped -> `other`. **Accept:** tests for `llama3.2`, list-valued licence, `other`, missing. **Verify:** same. Done 18 Oct 2026.
- [x] **G023** Scout BFS ingest with caps (depth 6, 300 nodes, 25 children per relation) writing I1-I5. **Accept:** ingesting OPEA creates OPEA, Xkev and meta-llama/Llama-3.2-11B-Vision-Instruct with two DERIVED_FROM edges at tier 2. **Verify:** `pytest tests/test_ingest.py` (recorded fixtures) and a live run. Done 18 Oct 2026. Live anonymous ingest returned those three models. Meta README/config came back 401 without `HF_TOKEN`.
- [x] **G024** README and config fetched at the model's sha; gated or 401/403 responses are skipped and recorded in `incomplete_reasons`. **Accept:** test with a gated fixture. **Verify:** same. Done 18 Oct 2026.
- [ ] **G025** Jobs: `POST /api/ingest`, `GET /api/jobs/{id}`, SSE `/events` as in API. **Accept:** SSE emits started, node, done for OPEA. **Verify:** `curl -N`.
- [ ] **G026** Children ingest (one level) for the demo set. **Accept:** after ingesting meta-llama/Llama-3.2-11B-Vision-Instruct with children, at least 25 descendants exist with tier-2 edges. **Verify:** `GET /api/models/.../descendants`.
- [ ] **G027** `data/prewarm.json` lists the demo set and the 40 eval models; prewarm runs as a background task on startup without blocking `/api/health`. **Accept:** health is green within 10 s of boot while prewarm continues. **Verify:** restart and time it.
- [ ] **G028** Lineage endpoint `GET /api/models/{owner}/{name}/lineage` (Q3, DISTINCT edges). **Accept:** Nephilim returns a DAG with multi-parent merge nodes and no duplicate edges. **Verify:** compare edge count with a set of (child, parent).
- [ ] **G029** Hub failure handling per FLOWS F15 (stale cache flag, 503 HUB_UNAVAILABLE with retry_after). **Accept:** test with the mock server down. **Verify:** `pytest tests/test_hub_down.py`.

## 3. Verdict core (M3, protect forever)
- [ ] **G030** Clause Loader (FLOWS F3): fetch `source_raw_url`, normalise, split with `split_regex`, extract by `locator`, cap 80 words, MERGE License and Clause nodes; unresolved -> quote null. **Accept:** at least 33 clauses resolve against live sources; `/api/health.clauses` shows the counts. **Verify:** call reload and read health.
- [ ] **G031** Q1 ancestry with tier filter returns every licence on every path, including through merges. **Accept:** for Nephilim, Q1 returns rows for all declared licences on its DAG. **Verify:** `pytest tests/golden/test_nephilim.py`.
- [ ] **G032** Q2 completeness: non-root tops make lineage incomplete with a human-readable reason. **Accept:** Sicarius FP8 with min_tier 2 is incomplete. **Verify:** golden test.
- [ ] **G033** `app/engine/clauses.py` evaluates `applies_when` (hq_in, market_in, commercial, mau_gt, distributes_weights, ancestor_multimodal, end_user_only, all, any, not, always) and `check` (name_prefix, card_mentions, license_file_present). **Accept:** table-driven unit tests for every operator. **Verify:** `pytest tests/test_clauses.py`.
- [ ] **G034** Decision order exactly FLOWS F1.7 (BLOCK, then CANNOT_DETERMINE, then OBLIGATIONS, then ALLOWED); null-quote clauses count as NEEDS_COUNSEL. **Accept:** unit tests for each branch. **Verify:** `pytest tests/test_verdict_logic.py`.
- [ ] **G035** Golden: OPEA, context DE commercial -> BLOCKED with clause `llama3_2.geo_eu_multimodal`, path OPEA -> Xkev -> meta-llama/Llama-3.2-11B-Vision-Instruct, `declared_differs: true`. **Verify:** `pytest tests/golden/test_opea.py`.
- [ ] **G036** Golden: OPEA, context US commercial -> ALLOWED_WITH_OBLIGATIONS including `llama3_2.built_with_notice` and `llama3_2.aup`. **Verify:** same file.
- [ ] **G037** Golden: a cc-by-nc-4.0 model in a commercial context -> BLOCKED by `ccbync.noncommercial`; non-commercial -> ALLOWED_WITH_OBLIGATIONS. **Verify:** golden test (fixture model chosen in `eval/models.csv`).
- [ ] **G038** Golden: `Qwen/Qwen2.5-7B-Instruct` (apache-2.0, root) in DE -> ALLOWED or ALLOWED_WITH_OBLIGATIONS depending on `distributes_weights`; never BLOCKED. **Verify:** golden test.
- [ ] **G039** Golden: a model with an `unknown` licence on its path -> CANNOT_DETERMINE with a reason. **Verify:** golden test.
- [ ] **G040** `POST /api/verdict` per API, with validation (FLOWS F1.1), freshness/queued behaviour (F1.2) and response type `Verdict`. **Accept:** schema test validates the response against the TypeScript-equivalent pydantic model. **Verify:** `pytest tests/test_verdict_api.py`.
- [ ] **G041** Alternatives (FLOWS F1.9) only for BLOCKED, from cached hub data, labelled "in our candidate set". **Accept:** OPEA in DE returns at least one alternative or the exact "No compliant alternative in our candidate set" message. **Verify:** golden test.
- [ ] **G042** Template explanation always available; optional LLM phrasing with 6 s timeout and daily budget, evidence-only prompt, never alters the verdict. **Accept:** test that a mocked LLM returning "ALLOWED" text does not change a BLOCKED verdict. **Verify:** `pytest tests/test_explain.py`.
- [ ] **G043** Disclaimer string present in every verdict response and every verdict view. **Verify:** test + UI check.
- [ ] **G044** FalkorDB is load-bearing: with FalkorDB stopped, `/api/verdict` returns 503 GRAPH_UNAVAILABLE and the web shows the banner (no answer from any cache). **Verify:** `docker compose stop falkordb` then curl; record a 10 s clip for the video.
- [ ] **G045** Every ClauseHit carries license, quote (or null), summary, source_url, section, path, tiers. **Accept:** schema test. **Verify:** golden tests.
- [ ] **G046** Response includes `cypher.q1` and `cypher.q2` (exact text) and `computed_ms`. **Verify:** API test.
- [ ] **G047** Web home page and verdict page per UI (all states: loading, queued with SSE progress, error, done; badge, declared-vs-inherited strip, context chips with Flip HQ, lineage graph, clause cards, alternatives, How we decided, actions, disclaimer). **Accept:** Playwright: paste OPEA, see BLOCKED for DE; flip to US, see amber. **Verify:** `npx playwright test verdict.spec.ts`.
- [ ] **G048** Latency: a cached verdict returns in under 1.5 s p95 end to end on the deployment. **Verify:** `scripts/bench.sh` 20 runs.
- [ ] **G049** **M3 milestone check**: on the public URL, from a private window on a phone, OPEA shows BLOCKED for DE and amber for US with path and quote. **Verify:** screenshot saved in `docs/evidence/m3.png`.

## 4. Resolver, algorithms and eval (M5)
- [ ] **G050** `eval/models.csv` (40 models per BLUEPRINT 12) and `eval/labels.json` (80 labels) written by a human before G033 is merged; `eval/labels.sha256` committed. **Accept:** git history shows labels committed before the clause engine. **Verify:** `git log --follow eval/labels.json`.
- [ ] **G051** Fingerprints (I5) written for every ingested model: weights sha256 per weight file, tokenizer sha, config fingerprint per BLUEPRINT 6.3. **Accept:** meta-llama/Llama-3.2-1B and unsloth/Llama-3.2-1B share `weights_sha256:68a2e4be76fa7094…`. **Verify:** Cypher in FalkorDB Browser.
- [ ] **G052** R1 WCC grouping exposed at `GET /api/algo/hidden-lineage`. **Accept:** a component contains meta-llama/Llama-3.2-1B and SicariusSicariiStuff/Llama-3.2-1B_Base_FP8. **Verify:** API call.
- [ ] **G053** R2/R3 inferred edges with the rules in FLOWS F4.2 and evidence text; never overwrite declared edges. **Accept:** Sicarius FP8 gets an inferred tier-1 edge to meta-llama/Llama-3.2-1B; alpindale/Llama-3.2-1B gets a mirror edge (conf 0.97). **Verify:** golden test.
- [ ] **G054** Strict mode (min tier 2): Sicarius FP8 -> CANNOT_DETERMINE; default mode -> licence-driven verdict. **Verify:** golden test.
- [ ] **G055** Hidden-lineage page per UI `/hidden-lineage` with Confirm buttons. **Verify:** Playwright.
- [ ] **G056** `eval/run_eval.py` runs 80 cases (default and strict) and writes `eval/report.json`. **Accept:** false ALLOW count = 0. **Verify:** run it; report committed.
- [ ] **G057** `eval/baseline_card_only.py`: declared-licence-only baseline always; card-only LLM baseline when a key is set. **Accept:** report contains both baselines. **Verify:** run it.
- [ ] **G058** `/eval` page per UI with labels hash. **Verify:** Playwright.
- [ ] **G059** Auditor batch sets `Model.declared_differs` for all hub models (needed by A1). **Accept:** OPEA and Xkev have `declared_differs = true`. **Verify:** Browser query.

## 5. Tenants, memory, MCP (M4)
- [ ] **G060** Tenant bootstrap (FLOWS F0.6) loads `kestrel.cypher` and `harbor.cypher` into empty graphs; all names carry "(fictional)". **Accept:** `GET /api/tenants` lists both. **Verify:** API call.
- [ ] **G061** Overview endpoint and `/companies` page show products, deployments, owners and latest verdict (T6). **Verify:** Playwright.
- [ ] **G062** Memory types are real and visible: episodic = Ruling/Event history; semantic = hub facts; procedural = `(:Playbook)` nodes per task kind seeded at bootstrap and linked by `(Task)-[:FOLLOWS]->(Playbook)`. **Accept:** README section "Memory" names each with a query. **Verify:** Browser queries.
- [ ] **G063** One graph per company and per sandbox on a single FalkorDB instance. **Accept:** `GRAPH.LIST` shows hub, tenant_kestrel, tenant_harbor and any sbx_*. **Verify:** redis-cli.
- [ ] **G064** Decision trace (T7) endpoint and drawer: ruling -> facts (model, commit sha linked to the Hub commit, licence, clause ids) -> events with who signed. **Verify:** Playwright.
- [ ] **G065** Sandbox (FLOWS F7) with GRAPH.COPY, token header, TTL, cleanup, limits. **Accept:** creating, using and expiring a sandbox works; fixed tenants reject writes with 403. **Verify:** `pytest tests/test_sandbox.py`.
- [ ] **G066** Tasks with leases (T5), states OPEN, CLAIMED, AWAITING_APPROVAL, DONE; events for every transition. **Verify:** `pytest tests/test_tasks.py`.
- [ ] **G067** Ruling writes are append-only (T1, T2) and honour `expected_ruling_id` with 409 STALE_RULING. **Accept:** concurrent test: two writers, one gets 409. **Verify:** `pytest tests/test_concurrency.py`.
- [ ] **G068** Handoff: Watcher -> Auditor (REVIEW_RULING) -> owner (APPROVE_RULING) linked by HANDED_OFF_FROM (FLOWS F9.7-8). **Verify:** integration test.
- [ ] **G069** Playbook steps shown on each task card in the UI. **Verify:** Playwright. *(cuttable)*
- [ ] **G070** MCP server mounted at `/mcp` exactly as BLUEPRINT section 3 (FastMCP, stateless_http, mounted after routes, lifespan). **Accept:** `initialize`, `tools/list`, `tools/call` succeed over HTTP. **Verify:** curl script in `scripts/mcp_smoke.sh`.
- [ ] **G071** `can_i_use` tool per API with the verbatim description and the text format in FLOWS F5.3. **Verify:** mcp_smoke.
- [ ] **G072** `explain` and `lineage` tools. **Verify:** mcp_smoke.
- [ ] **G073** Claude Code connects with `claude mcp add --transport http modelbrain <api>/mcp` and calls `can_i_use` unprompted when asked to add a model. **Accept:** screen recording saved for the video. **Verify:** recording in `docs/evidence/`.
- [ ] **G074** `proof_path` tool and endpoint (A4 shortestPath; NULL means no path). **Verify:** golden test for a path and a no-path case.
- [ ] **G075** `relabel_hubs` tool and endpoint (A1 PageRank filtered by declared_differs). **Accept:** princeton-nlp/gemma-2-9b-it-SimPO or Xkev appears in the top 20 after prewarm. **Verify:** API call.
- [ ] **G076** `chokepoints` tool and endpoint (A2 betweenness). **Verify:** API call.
- [ ] **G077** `families` tool and endpoint (A3 label propagation). **Verify:** API call.
- [ ] **G078** Persistent conversation history: every MCP call and web check with a tenant writes `(Conversation)-[:HAS_TURN]->(Turn)` and `(Turn)-[:PRODUCED]->(Ruling)` when a ruling is written; `GET /api/tenants/{t}/conversations`. **Verify:** integration test.
- [ ] **G079** Stretch: "Ask the company brain" box on `/companies` that answers a fixed set of 8 templated questions over the tenant graph (who owns X, which deployments reopened this week, which rulings rest on model Y, ...); optional QueryWeaver text-to-Cypher behind a feature flag. **Verify:** Playwright. *(cuttable)*

## 6. Watcher, fan-out, compounding, loop, CI (M6)
- [ ] **G080** Watcher job (FLOWS F9.1-6): sha check, re-ingest, Snapshot, diff, descendants (D1), reopen (T3, T4), FanOut record. **Accept:** changing a fixture model's sha reopens Kestrel's ruling and creates a task for its owner. **Verify:** integration test.
- [ ] **G081** `POST /api/watch/check` "check now". **Verify:** API call.
- [ ] **G082** Approve/reject flow writes a new ruling with SUPERSEDES and a signed Event (FLOWS F9.8). **Verify:** integration test.
- [ ] **G083** Fix leverage (D2) shown on descendants and replay views. **Verify:** API call.
- [ ] **G084** Xkev replay endpoint and page (FLOWS F11) with the real commits (`dfdcec1f9f`, `7ee73286de`, `213eb383f1`, `e8c2529775`) and discussion 12. **Accept:** page shows 9 of 9 children did not inherit the fix. **Verify:** Playwright.
- [ ] **G085** Publisher (FLOWS F8, P1) with salted hashes; tier 3 at two independent confirmers; reopen of affected rulings. **Accept:** confirm from two tenants raises the Sicarius edge to tier 3 and Harbor's strict verdict changes. **Verify:** integration test.
- [ ] **G086** Hub privacy: a test asserts no hub node or relationship property contains a tenant name. **Verify:** `pytest tests/test_hub_privacy.py`.
- [ ] **G087** Discussions ingested for demo models as `(:Discussion)-[:ABOUT]->(:Model)` with outcomes. **Verify:** Browser query.
- [ ] **G088** Notifier drafts (FLOWS F10.2) with template text and approval tasks; posting only to `HF_POST_ALLOWLIST` with `HF_WRITE_TOKEN`; otherwise "ready to copy". **Accept:** a test proves posting to a non-allowlisted repo is impossible. **Verify:** `pytest tests/test_notifier.py`.
- [ ] **G089** Live loop on our own test repo (README + config only, "test fixture, contains no weights"): post, edit card, check now, tier 4, reopened rulings, Outcome FIXED. **Verify:** `/live-loop` run recorded. *(cuttable: keep replay)*
- [ ] **G090** GitHub Action `actions/modelbrain-check` (FLOWS F12) with job summary and exit codes; never fails CI when our API is unreachable unless configured. **Verify:** demo repo PR red with OPEA, green with an allowed model. *(cuttable)*
- [ ] **G091** `POST /api/ci/check`. **Verify:** API test.
- [ ] **G092** Watchlist file `data/watchlist.json` (Xkev, its children, meta-llama roots in the demo). **Verify:** watcher log.
- [ ] **G093** Resolver runs after prewarm and nightly. **Verify:** `/api/admin/resolver/last`.
- [ ] **G094** Sandbox users can run "check now" only for models in their sandbox's deployments. **Verify:** test.
- [ ] **G095** Eval re-run after M6 still has false ALLOW = 0. **Verify:** report.
- [ ] **G096** All web pages in UI exist and link from the nav. **Verify:** Playwright crawl.
- [ ] **G097** Copy rules (UI "Copy rules") enforced: a test greps `apps/web` and API templates for "violat", "illegal", "infring". **Verify:** `pytest tests/test_copy_rules.py`.
- [ ] **G098** `/how-it-works` page per UI. **Verify:** visual check. *(cuttable: move to README)*
- [ ] **G099** `/mcp` page per UI. **Verify:** visual check.

## 7. Hardening and deployment (M7)
- [ ] **G100** Production deployment: Vercel (web), Railway (api, falkordb with volume, requirepass, private networking, one api replica). **Verify:** smoke.sh green.
- [ ] **G101** Persistence: restart the falkordb service; hub, tenants and rulings survive. **Verify:** before/after counts.
- [ ] **G102** Local path: README "Run locally" works on a clean machine with Docker only (`docker compose up`, `npm run dev -- -p 3001`). **Verify:** a teammate follows it from scratch.
- [ ] **G103** Rule 3 evidence in README: the G044 clip plus a sentence explaining that every answer is a FalkorDB query. **Verify:** README.
- [ ] **G104** Load: 50 concurrent cached verdicts complete with no errors and p95 under 2 s; 20 concurrent ruling writes produce correct 409s. **Verify:** `scripts/load.py` output saved.
- [ ] **G105** Rate limits per API "Conventions" return 429 with `retry_after_s`. **Verify:** test.
- [ ] **G106** Input validation rejects bad model ids and countries with 422. **Verify:** test.
- [ ] **G107** Prewarm complete on production before judging; demo models answer from cache. **Verify:** smoke.sh timing.
- [ ] **G108** Mobile layout of every page at 375 px with no horizontal scroll. **Verify:** Playwright screenshots.
- [ ] **G109** Error and empty states for every page (no data, sandbox expired, hub down, graph down). **Verify:** Playwright with mocked failures.
- [ ] **G110** Security: tokens compared in constant time; no tokens in logs or the graph; admin endpoints require `ADMIN_TOKEN`. **Verify:** test.

- [ ] **G111** Hub snapshot export: `make export` writes the hub and tenant graphs to `exports/*.cypher` (or RDB via `BGSAVE` copy) so the demo can be restored in minutes. **Verify:** restore into a fresh container and run smoke.sh.
- [ ] **G112** Uptime check: a free external monitor (or a GitHub Actions cron) hits `/api/health` every 30 minutes during the judging window and alerts the team. **Verify:** first alert test.
- [ ] **G113** Judge-day runbook `docs/RUNBOOK.md`: how to restart services, re-seed tenants, re-run prewarm, rotate tokens, and what to do if the Hub rate-limits. **Verify:** a teammate restarts the stack using only the runbook.
- [ ] **G114** Cost guard: Railway spend limit set; LLM daily budget enforced; sandbox cap 50. **Verify:** settings screenshots in `docs/evidence/`.

## 8. Submission (M8)
- [ ] **G115** Public GitHub repository with LICENSE (MIT, after the team agrees, rule 15). **Verify:** open the repo logged out.
- [ ] **G116** README "Run locally" and "Deploy" sections complete (rule 10). **Verify:** G102.
- [ ] **G117** README "Graph data model" with BLUEPRINT 5.1-5.3 tables and a diagram, plus a dependencies list (rule 9). **Verify:** README review.
- [ ] **G118** README "Queries and algorithms": links `docs/queries.cypher`, explains Q1, Q2, R1, D1, P1, T3, A1-A4 in plain words, and a "Explore in FalkorDB Browser" walkthrough with two screenshots (hub lineage, tenant ruling trace). **Verify:** README review.
- [ ] **G119** Demo video (3 minutes) following BLUEPRINT section 15, uploaded and linked. **Verify:** link opens logged out.
- [ ] **G120** README "Built with AI assistance" disclosure (Claude for research and specification, Cursor for implementation; humans wrote eval labels, reviewed code, verified sources) (rule 11). **Verify:** README review.
- [ ] **G121** Submission form completed before 18 Oct 2026, 23:00 IST: repo, video, live URL, tracks (Track 1 primary; Track 2; Track 3), team members registered (rule 1, 5, 7). **Verify:** confirmation screenshot.
- [ ] **G122** `docs/EXPLAINER.md` rehearsed by every team member (rule 12). **Verify:** each member explains Q1, R1 and D1 aloud.
- [ ] **G123** Blog post draft for the side prize, published after submission. *(cuttable)*
- [ ] **G124** No competitor names or comparisons in the public repo, README, video or blog (rules 16-17). **Verify:** grep the repo for names listed in the private notes.
- [ ] **G125** Final checklist: BLUEPRINT section 17 fully ticked; every goal here done or struck through with a reason. **Verify:** review this file.

## 9. Add-ons (after M6 unless noted; all cuttable in the order of BLUEPRINT section 18)
- [ ] **G126** OpenRouter LLM gateway in `app/llm.py` (`OPENROUTER_API_KEY`, `LLM_MODEL`), used by explanations, drafts and the Ask router; 6 s timeout; daily budget; template fallback. Build in Block 2. **Verify:** explanation works with the key and without it.
- [ ] **G127** Multi-LLM card-only baseline over `EVAL_BASELINE_MODELS` (comma-separated OpenRouter ids, checked against `GET /api/v1/models` at run time). **Accept:** `/eval` compares the graph with each model. **Verify:** report.
- [ ] **G128** Catalogue sync (FLOWS F16.1): providers (O1), hosted models with `hugging_face_id` (O2), endpoints for the hosted demo set (O3). **Accept:** at least 100 providers and 150 hosted models in the hub. **Verify:** Browser count query.
- [ ] **G129** Hosted verdict (FLOWS F16.2-5) with residency check (O4) and the NEEDS_COUNSEL wording for the end-user exemption. **Accept:** golden test: `meta-llama/llama-4-scout` hosted, residency EU -> verdict + provider list or the no-provider proof. **Verify:** golden test.
- [ ] **G130** `where_can_i_run` MCP tool and `/api/hosted/...` endpoints. **Verify:** mcp_smoke.
- [ ] **G131** Verdict page "How do you run it?" switch and providers panel (UI add-on). **Verify:** Playwright.
- [ ] **G132** Licence text watch (FLOWS F17): L1, L2, T8, T4; daily job and admin trigger. **Accept:** changing a fixture text sha reopens the Kestrel ruling that rests on it. **Verify:** integration test.
- [ ] **G133** Web fetcher adapter `app/fetch.py` with backends `httpx` (default), `firecrawl` (`FIRECRAWL_API_KEY`) and `anakin` (`ANAKIN_API_KEY`); identical normalised output; verify each provider's current API before enabling it. **Verify:** unit test with the httpx backend; manual check for any enabled provider.
- [ ] **G134** Custom licence resolution for `other` + `license_link` (BLUEPRINT section 18). **Accept:** a fixture card linking to the Llama 3.2 licence text resolves to `llama3_2` with `source: "matched_text"`; an unknown text stays NEEDS_COUNSEL. **Verify:** golden test.
- [ ] **G135** Ask the company brain (FLOWS F18) with 8 templates, LLM tool selection with schema validation, keyword fallback, Turn records. **Accept:** "Who owns the claims vision deployment?" returns Lena Vogt (fictional) with the Cypher. **Verify:** integration test.
- [ ] **G136** `ask_company` MCP tool. **Verify:** mcp_smoke.
- [ ] **G137** Voice (FLOWS F19) on the Ask box and verdict page. **Verify:** manual test in Chrome. *(cut first)*
- [ ] **G138** README and video mention the add-ons that shipped, and only those. **Verify:** README review.
