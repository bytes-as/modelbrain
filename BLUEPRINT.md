# ModelBrain v3: build blueprint

The single source of truth for building ModelBrain v3 for **Graph Hacks: Context for AI Agents** (WeMakeDevs x FalkorDB).
Submissions close **Sunday 18 Oct 2026, 11:59 PM IST**. Implementation: Cursor. Product owner and reviewer: Claude (this spec's author) with the team.

## 0. Read me first (document map)
| File | What it is | Authority |
|---|---|---|
| `AGENTS.md` | the rules every coding agent follows | binding |
| `BLUEPRINT.md` (this file) | product, architecture, data model, logic | binding |
| `docs/GOALS.md` | 151 numbered goals with acceptance tests: the work list Cursor executes in order | binding; the definition of done |
| `docs/ADDENDUM_WEIGHT_DNA.md` | weight DNA, merge DNA, GGUF DNA, canonical ids (M6b) | binding (merged by G139) |
| `docs/FLOWS.md` | every runtime flow step by step, with failure handling | binding |
| `docs/API.md` | endpoint, type, error and MCP tool contract | binding |
| `docs/UI.md` | every page, state and line of copy | binding |
| `docs/queries.cypher` | every Cypher query, tested on FalkorDB | binding |
| `docs/REQUIREMENTS.md` | every hackathon rule and judging signal mapped to goals | binding |
| `docs/TASKS.md` | the hour-by-hour board (summary of GOALS by block) | guidance |
| `docs/OPEN_POINTS.md` | what was verified, what is deferred to the end, and why | guidance |
| `docs/EXPLAINER.md` | the 2-minute talk track every team member must be able to give | guidance |
| `data/*` | clause table, EU list, roots, alternatives, demo tenants | binding |
If two files disagree, the order of precedence is: AGENTS.md, GOALS.md, API.md, FLOWS.md, BLUEPRINT.md, UI.md, the rest. Record the conflict in `docs/TASKS.md` under "Questions for the owner".

## 0.1 FalkorDB is the heart (prime constraint)
The sponsor is FalkorDB. The FAQ and rule 2 require it to be the primary graph database supporting a central part of the product; rule 3 disqualifies a graph that is decoration. In ModelBrain:
- **Every answer is a FalkorDB query.** Verdicts (Q1, Q2), lineage (Q3), fan-out (D1, D2), proof paths (A4), rankings (A1, A2), families (A3), hidden lineage (R1 WCC) and every memory read (T3, T6, T7) run in FalkorDB. There is no other database. Caches hold raw Hub HTTP responses only, never graph answers.
- **Every memory write is a FalkorDB write**: rulings, facts, events, tasks, conversations, confirmations, snapshots.
- **We use the sponsor's headline features on screen**: multi-graph tenancy (hub + one graph per company + per-visitor sandboxes via `GRAPH.COPY` on one instance), Cypher, all five algorithm families named on the hackathon page (shortest path, PageRank, centrality, connected components, community detection), MCP, and FalkorDB Browser (README walkthrough).
- **Proof**: goal G044 is a test that stops FalkorDB and shows the verdict endpoint returns 503 instead of an answer.

---

## 1. What we are building, in one paragraph

ModelBrain is the control plane for a company's AI supply chain. A coding agent, a CI pipeline, or a person asks: **"Can this team ship this product on this Hugging Face model, for users in these countries, and who must sign off?"** ModelBrain pulls the model's real ancestry from the Hugging Face Hub into FalkorDB, carries licence obligations down every finetune, adapter, quantisation and merge edge, unmasks re-uploads that hide their parent by matching file hashes, and returns a verdict with the path and the quoted clause. It remembers every ruling per company, learns from every confirmed fact in a shared public layer, and when an upstream author changes a model card, every ruling in every company that rested on the old fact reopens and goes to its owner.

### The three things a judge must see
1. **Claude Code asks ModelBrain over MCP** whether it may load `OPEA/Llama-3.2V-11B-cot-int4-sym-inc` for a Berlin company. Answer: **BLOCKED**, with the path `OPEA -> Xkev -> meta-llama/Llama-3.2-11B-Vision-Instruct -> Llama 3.2 use policy` and the quoted clause. The card says apache-2.0. Flip HQ to the US: **ALLOWED WITH OBLIGATIONS** (the Llama 3.2 notice and use policy; more if the product redistributes weights).
2. **The Xkev replay**: a licence discussion opened on 9 Jul 2025; 130 days later the author added Meta's licence file, yet the card still says apache-2.0 and none of its 9 children picked up the fix. Our watcher shows the fix landing upstream and the 9 children lighting up.
3. **Compounding across companies**: the resolver unmasks a re-upload that names no parent (identical weights or tokenizer and config hashes to Meta's original). Company A confirms the edge; company B's verdict flips from CANNOT DETERMINE to BLOCKED. Two FalkorDB graphs side by side on one instance.

### Tracks
- **Primary: Track 1, Agents That Act on Connected Data.** Multi-hop ancestry, graph algorithms as tools (WCC, bounded paths), tool selection through MCP, actions (block a PR, draft a card fix), explainable results.
- **Also name: Track 2** (per-company graphs, agents handing off tasks, shared state, rulings remembered across sessions) **and Track 3** (who owns each deployment, decisions traced to the clause and commit that justified them, knowledge kept current by reopen-on-change).
- Build Track 1 pieces first; they are also the hour-8 core. Do not build a docs/chat ingester for Track 3.

---

## 2. Non-negotiables (rules, ethics, wording)

1. **FalkorDB is load-bearing.** Every verdict comes from a Cypher traversal in FalkorDB. If FalkorDB is removed, the product must not work. Never compute ancestry in Python and only store it in the graph.
2. **The model suggests, the graph decides.** Verdicts are deterministic code over graph results. An LLM may only (a) phrase an explanation from the evidence IDs it is given, (b) draft a discussion text. If no LLM key is configured, template text is used and the product still works.
3. **Human approval before any outward action.** Posting a Hugging Face discussion, opening an issue, failing a real CI run in someone else's repo: always behind an Approve click by an authenticated human. **Never post to third-party repos from the public demo.** Live posting is allowed only to repos on `HF_POST_ALLOWLIST` (our own test repos).
4. **Append-only history.** Rulings, confirmations and approvals are never updated in place. A changed answer is a new ruling that supersedes the old one; reopening is an event node.
5. **Wording.** Say "the declared licence differs from the obligations inherited from its ancestors", "this use may not be permitted by the upstream licence", "needs counsel". Never "violating", "illegal", "infringing", or anything that accuses a named person or company. Show a footer on every verdict: "Automated screening, not legal advice."
6. **Data.** Public Hugging Face Hub metadata only (model cards, tags, file hashes, commit history, discussions). Licence quotes are extracted at runtime from the official licence texts by the Clause Loader (`docs/FLOWS.md` F3); the repo stores only short locators and source URLs, never licence text. Demo companies, people and products are fictional and labelled "(fictional)".
7. **Do not re-upload anyone's weights.** Our own test repos contain only a README and a config file; they declare a `base_model` for the loop demo and say "test fixture, contains no weights".
8. **README must include** (rule 10): setup instructions, the graph data model, the Cypher queries and algorithms the product depends on, the demo video link, the live URL, the tracks entered, and a disclosure that AI coding assistants were used (rule 11). Everyone on the team must be able to explain the graph model and queries (rule 12).

---

## 3. Architecture

```
               Vercel (Next.js web app)                      Coding agents (Claude Code, Cursor)
                        |                                              |  MCP (streamable HTTP)
                        v                                              v
        +------------------------------------------- Railway (always-on) ------------------------------+
        |  services/api  (Python 3.12, FastAPI)                                                          |
        |   - REST API (/api/*)          - MCP server (/mcp)           - CI check (/api/ci/check)        |
        |   - Agents: Scout, Resolver, Auditor, Watcher, Notifier, Publisher (in-process workers)         |
        |   - APScheduler: watcher every 10 min, sandbox cleanup every 15 min                             |
        |   - Hugging Face client: httpx + on-disk/redis cache, HF_TOKEN (read), HF_WRITE_TOKEN (allowlist) |
        +------------------------------------------------------------------------------------------------+
                        |  falkordb-py (Redis protocol)
                        v
        FalkorDB (Docker image falkordb/falkordb on Railway with a persistent volume)
          graph "hub"                  shared public layer: models, licences, clauses, fingerprints, evidence
          graph "tenant_kestrel"       fictional EU company: teams, people, products, deployments, rulings, tasks
          graph "tenant_harbor"        fictional US company
          graph "sbx_<id>"             per-visitor sandbox copied from a tenant template, deleted after 2 h

        GitHub Action (actions/modelbrain-check) --HTTPS--> /api/ci/check
```

### Hosting decision (verified 17 Oct 2026)
- **Web app on Vercel** (Hobby is fine). Vercel Functions on Hobby allow up to 300 s with fluid compute, but Hobby cron jobs run at most once per day, and Vercel cannot host FalkorDB. So Vercel serves only the Next.js frontend; it calls the API over HTTPS.
- **API, agents and MCP on Railway** (or Fly.io/Render with an always-on instance; avoid free tiers that sleep, because judges may open the link days later and a 50 s cold start looks broken).
- **FalkorDB on Railway in Docker** (`falkordb/falkordb:latest`, persistent volume, `appendonly yes`). Do **not** use the FalkorDB Cloud free tier for the judged deployment: it has 100 MB, no backups, stops after 1 day idle and is deleted after 7 days idle, and judging will likely happen after the deadline. FalkorDB Cloud Startup ($73/month) is the managed alternative if needed.
- Expected cost for the judging window: about $5 to $15 on Railway.
- Keep `docker compose up` working locally too: the rules accept full local setup when a deployment is unavailable.

### Tech choices
| Layer | Choice | Why |
|---|---|---|
| Graph | FalkorDB 4.x via `falkordb` Python client | the sponsor; multi-graph tenancy; Cypher; `algo.WCC` |
| API | FastAPI, pydantic v2, httpx, APScheduler, slowapi (rate limits) | quick, typed, async HTTP to the Hub |
| MCP | official `mcp` Python SDK **pinned `mcp>=1.10,<2`** (verified 1.30.0), `FastMCP("modelbrain", stateless_http=True)`, mounted with `app.mount("/", mcp.streamable_http_app())` after all FastAPI routes, lifespan runs `mcp.session_manager.run()`; endpoint `/mcp` | Claude Code and Cursor connect over HTTP. mcp 2.x renamed FastMCP to MCPServer; do not upgrade during the event |
| LLM (optional) | OpenRouter (`OPENROUTER_API_KEY`, model from `LLM_MODEL`, default a Claude Haiku-class model) for explanation, draft text, the Ask router and eval baselines only | one gateway, any model; template fallback when no key |
| Web | Next.js (App Router, TypeScript), Tailwind, `react-force-graph-2d` (or Cytoscape.js) | graph visualisation of ancestry and fan-out |
| Tests | pytest with a FalkorDB service container; Playwright smoke test for the web app | golden verdicts must not regress |
| CI gate | composite GitHub Action (bash + python) | judges can see a red PR |

Verified on 18 Oct 2026 against `falkordb/falkordb:latest` (module version 42201): every query in `docs/queries.cypher` runs, including `*0..6` zero-length paths, `algo.WCC`, `algo.pageRank`, `algo.betweenness`, `algo.labelPropagation`, `shortestPath` (NULL when no path), `algo.SSpaths`, and `GRAPH.COPY` (fails if the destination exists). MERGE on indexed `id` gives idempotent writes, so no unique constraints are needed. The MCP mount above was verified with mcp 1.30.0 (`initialize`, `tools/list`, `tools/call`).

FalkorDB container facts (verified): data directory `/var/lib/falkordb/data`; Redis options via `REDIS_ARGS` (use `--appendonly yes --requirepass <password>`); module options via `FALKORDB_ARGS`, whose image default is `MAX_QUEUED_QUERIES 25 TIMEOUT 1000 RESULTSET_SIZE 10000`. The default 1 s query timeout is too tight for ingest batches: set `TIMEOUT 5000`. The image starts with `--protected-mode no` and no password, so on Railway always set `requirepass` and keep FalkorDB on private networking only.

---

## 4. Data sources (Hugging Face Hub, all public)

All endpoints below were exercised during research on 17 Oct 2026 unless marked "verify".

| Need | Endpoint | Notes |
|---|---|---|
| Model metadata | `GET https://huggingface.co/api/models/{id}` | `cardData.license`, `cardData.base_model` (string or list), `tags` (contains `license:...` and `base_model:finetune:X`, `base_model:adapter:X`, `base_model:merge:X`, `base_model:quantized:X`), `sha`, `lastModified`, `createdAt`, `pipeline_tag`, `gated` |
| File hashes | `GET https://huggingface.co/api/models/{id}?blobs=true` | each `siblings[]` item has `rfilename`, `size`, `blobId`, and `lfs.sha256` for LFS files. Verified: `unsloth/Llama-3.2-1B` and `meta-llama/Llama-3.2-1B` share `model.safetensors` sha256 `68a2e4be76fa7094...`; works on gated repos without accepting the gate |
| Children | `GET https://huggingface.co/api/models?filter=base_model:{relation}:{id}&limit=100` with relation in finetune, adapter, merge, quantized | e.g. Llama-3.2-11B-Vision-Instruct has 492 direct descendants |
| Commit history | `GET https://huggingface.co/api/models/{id}/commits/main` | list of `{id, title, message, date, authors}` (verified); used for the Xkev replay and for diffing |
| File at a revision | `GET https://huggingface.co/{id}/raw/{sha}/README.md` and `/config.json` | gated repos need a token whose account accepted the gate; prefer non-gated mirrors for config fingerprints |
| Discussions | `GET https://huggingface.co/api/models/{id}/discussions` and `/discussions/{num}` | `{discussions:[{num, title, status, createdAt, author, isPullRequest, numComments, ...}], count, numClosedDiscussions, start}` (verified); posting needs a write token and is allowlist-only |
| Rate limits | measured: about 500 requests per 5 minutes anonymous | always send `HF_TOKEN`; cache every response; cap each ingest |

Ingestion caps: depth 6, 300 nodes per request, 25 children per relation per node in "fan-out preview" mode, full children only for the curated demo set. Cache metadata for 6 h, file hashes until the model `sha` changes.

### Verified demo facts (re-checked by two independent panels)
- `OPEA/Llama-3.2V-11B-cot-int4-sym-inc` declares apache-2.0; its base `Xkev/Llama-3.2V-11B-cot` declares apache-2.0; that model's base is `meta-llama/Llama-3.2-11B-Vision-Instruct`.
- `Xkev/Llama-3.2V-11B-cot`: discussion 12 "License compatibility" opened 2025-07-09; on 2025-11-16 the author added the Llama 3.2 notice and `LICENSE_llama.txt`; the card still says `license: apache-2.0`; its 9 direct children all still declare apache-2.0.
- Llama 3.2 Vision: of 492 direct descendants, 52 relabel to apache or MIT and 260 declare no licence.
- Undeclared lineage: `SicariusSicariiStuff/Llama-3.2-1B_Base_FP8` and `shuyuej/Llama-3.2-1B-GPTQ` declare apache-2.0, name no parent, and share config fingerprint and tokenizer hash with `meta-llama/Llama-3.2-1B`; `alpindale/Llama-3.2-1B` names no parent and has a weights file byte-identical to Meta's. 139 of the top 300 Hub search hits for "Llama-3.2-1B" name no parent.
- Relabel hub: `princeton-nlp/gemma-2-9b-it-SimPO` declares MIT on a Gemma model; 208 of its 263 children also say MIT.
- Merge-heavy example: `grimjim/llama-3-Nephilim-v1-8B` has 48 ancestors, 11 multi-parent merges, 7 different declared licences, 10+ levels.

---

## 5. Graph model

FalkorDB cannot query across graphs, so the app joins graphs in code: the **hub** answers "what does this model inherit", the **tenant** graph answers "who uses it, under which context, and what did we decide".

### 5.1 Graph `hub` (shared, public facts only)

Nodes
| Label | Key properties |
|---|---|
| `Model` | `id` (unique, canonical Hub id from `GET /api/models/{id}`; see section 6.5), `sha`, `declared_license` (raw string or null), `pipeline_tag`, `created_at`, `last_modified`, `gated` (bool), `is_root` (bool, official base from an allowlisted org), `multimodal` (bool), `ingested_at`, `card_has_llama_notice` (bool), `has_license_file` (bool), `name_starts_with`, `declared_differs` (bool), `aliases` (list of non-canonical ids that redirect here), `dna_reference` (bool; true for ids in `data/dna_references.json`), `dna` (vecf32, 1024), `dna_sig`, `dna_status`, `dna_at`, `format` (`safetensors` or `gguf`), `gguf_file`, `gguf_license`, `gguf_basename` |
| `License` | `key` (normalised: `llama3_2`, `apache-2.0`, `gemma`, `mit`, `cc-by-nc-4.0`, `unknown`, `other`), `name`, `url` |
| `Clause` | `id` (e.g. `llama3_2.geo_eu_multimodal`), `kind`, `effect` (BLOCK, OBLIGATION, NEEDS_COUNSEL), `applies_when` (JSON string), `check` (JSON string or null), `summary`, `quote` (extracted at load time from the official source; null if unresolved), `locator`, `source_url`, `source_raw_url`, `section` |
| `TenantRegistry` | `name` (graph name of each fixed tenant; no usage data) |
| `Sandbox` | `name`, `expires_at` (no token stored) |
| `ClauseLoad` / `FanOut` / `DnaCrawl` | audit records of loader runs, fan-out runs and DNA crawl jobs |
| `Fingerprint` | `key` (unique: `<kind>:<value>`), `kind` (`weights_sha256`, `tokenizer_sha`, `config_fp`, `vocab_dna`), `value` |
| `Discussion` | `key` (`<model_id>#<num>`), `title`, `status`, `opened_at`, `closed_at`, `url` |
| `Outcome` | `id`, `kind` (FIXED, PARTIAL, REFUSED, SILENT), `days`, `observed_at`, `evidence_url` |
| `Snapshot` | `id` (`<model_id>@<sha>`), `model_id`, `sha`, `declared_license`, `observed_at` (one per observed revision; append-only) |

Relationships
| Type | From -> To | Properties |
|---|---|---|
| `DERIVED_FROM` | `Model` -> `Model` (child to parent) | `relation` (finetune, adapter, merge, quantized, mirror, inferred), `source` (declared, inferred), `method` (`weights`, `weights_merge`, or null for card/hash edges), `conf` (0..1), `tier` (see below), `evidence` (string), `weights_sim`, `share` (merge edges), `weights_share`, `weights_r2`, `confirmations` (int), `confirmers` (list of salted tenant hashes) |
| `DECLARES` | `Model` -> `License` | `as_of_sha`, `source` (`declared`, `gguf_meta`, `matched_text`) |
| `IMPOSES` | `License` -> `Clause` | |
| `HAS_FP` | `Model` -> `Fingerprint` | |
| `ABOUT` | `Discussion` -> `Model` | |
| `RESULTED_IN` | `Discussion` -> `Outcome` | |
| `OBSERVED` | `Model` -> `Snapshot` | |

Edge tiers (trust grows over time; this is the compounding layer)
| Tier | Meaning | Set by |
|---|---|---|
| 0 | weak inference (config fingerprint only, or weight similarity between `DNA_RELATED_MIN` and `DNA_DERIVED_MIN`) | Resolver / weight DNA (F20) |
| 1 | strong inference (identical weights sha256, tokenizer + config match, or weight similarity >= `DNA_DERIVED_MIN`) | Resolver / weight DNA (F20) |
| 2 | declared on the model card or tags | Scout |
| 3 | confirmed by at least 2 independent tenants, or by public evidence | Publisher |
| 4 | confirmed by the model author (card updated to declare it) | Watcher |

Default verdicts use tier >= 1. **Strict mode** uses tier >= 2 and answers CANNOT DETERMINE wherever a parent is missing or only inferred.

### 5.2 Graph `tenant_<slug>` (private per company; also the sandbox template)

Nodes
| Label | Key properties |
|---|---|
| `Company` | `slug`, `name` ("(fictional)" suffix), `hq_country` (ISO-2), `eu` (bool), `mau` (int) |
| `Team` | `id`, `name` |
| `Person` | `id`, `name`, `role` (engineer, legal, owner) |
| `Product` | `id`, `name`, `commercial` (bool), `markets` (list of ISO-2), `distributes_weights` (bool) |
| `Deployment` | `id`, `model_id`, `pinned_sha`, `env` (prod, staging) |
| `Ruling` | `id`, `verdict` (ALLOWED, ALLOWED_WITH_OBLIGATIONS, BLOCKED, CANNOT_DETERMINE), `strict` (bool), `created_at`, `hub_sha_set` (list), `explanation` |
| `Fact` | `id`, `model_id`, `sha`, `license_key`, `clause_ids` (list), `edge_tiers` (list) (a snapshot copy of what the ruling relied on) |
| `Event` | `id`, `kind` (REOPENED, SUPERSEDED, APPROVED, REJECTED, CONFIRMED_EDGE), `at`, `reason` |
| `Task` | `id`, `kind` (REVIEW_RULING, APPROVE_RULING, APPROVE_POST, CONFIRM_EDGE), `state` (OPEN, CLAIMED, AWAITING_APPROVAL, DONE), `lease_until`, `created_by_agent`, `proposed_verdict`, `proposed_ruling_json` |
| `Draft` | `id`, `target_repo`, `title`, `body`, `posted_url` |
| `Conversation` | `id`, `channel` (mcp, web), `started_at` |
| `Turn` | `id`, `tool`, `args_json`, `verdict`, `at` |
| `Playbook` | `kind` (REVIEW_RULING, APPROVE_RULING, APPROVE_POST, CONFIRM_EDGE), `steps` (list of strings) - procedural memory the agents follow |

Relationships
`(Team)-[:PART_OF]->(Company)`, `(Person)-[:MEMBER_OF]->(Team)`, `(Team)-[:OWNS]->(Product)`, `(Person)-[:OWNS {from,until}]->(Deployment)`, `(Product)-[:RUNS]->(Deployment)`, `(Ruling)-[:FOR]->(Deployment)`, `(Ruling)-[:RESTS_ON]->(Fact)`, `(Ruling)-[:SUPERSEDES]->(Ruling)`, `(Event)-[:ON]->(Ruling)`, `(Person)-[:SIGNED]->(Event)`, `(Task)-[:ABOUT]->(Ruling)`, `(Task)-[:ASSIGNED_TO]->(Person)`, `(Task)-[:HANDED_OFF_FROM]->(Task)`, `(Draft)-[:FOR_TASK]->(Task)`, `(Conversation)-[:HAS_TURN]->(Turn)`, `(Turn)-[:PRODUCED]->(Ruling)`, `(Task)-[:FOLLOWS]->(Playbook)`.

### 5.3 Privacy rule for compounding
The hub never stores which tenant uses which model. Tenant confirmations reach the hub only through the Publisher, which writes a salted hash of the tenant id into `DERIVED_FROM.confirmers` and promotes the tier when 2 distinct hashes exist. Our own crawler also writes facts, so the presence of a model in the hub reveals nothing about any customer.

---

## 6. Core logic

### 6.1 Clause evaluation (deterministic)
Inputs: the list of `(ancestor, hops, license, clause)` rows from query Q1, the product context, and the model's own properties.

Context schema:
```json
{ "hq_country": "DE", "markets": ["DE","FR"], "commercial": true, "mau": 120000,
  "distributes_weights": false, "end_user_only": false }
```
`applies_when` is a tiny JSON rule language, evaluated in Python (`services/api/app/engine/clauses.py`):
- `{"hq_in": "EU"}` (EU means the 27 member states in `data/eu_countries.json`)
- `{"market_in": "EU"}`, `{"commercial": true}`, `{"mau_gt": 700000000}`, `{"distributes_weights": true}`
- `{"ancestor_multimodal": true}` (true if the ancestor that carries the licence is multimodal)
- `{"all": [ ... ]}`, `{"any": [ ... ]}`, `{"not": { ... }}`, `{"always": true}`

`check` (optional) lets an obligation be verified automatically on the queried model:
- `{"name_prefix": "Llama"}` checks `Model.name_starts_with`
- `{"card_mentions": "Built with Llama"}` checks `card_has_llama_notice`
- `{"license_file_present": true}` checks `has_license_file`
Each obligation is reported as SATISFIED, NOT_SATISFIED or NOT_CHECKABLE.

### 6.2 Verdict
1. **Ensure ingested.** If the model or any ancestor is missing or stale, Scout ingests (section 7). Return a job id and stream progress if this takes more than about 2 s.
2. **Lineage completeness.** Walk up with Q1. A node is a **root** if `is_root` is true (allowlisted official orgs: meta-llama, google, mistralai, Qwen, microsoft, tiiuae, bigscience, EleutherAI, allenai, stabilityai, openai-community, ...). If the walk ends at a non-root node with no parent edge at the required tier, lineage is **incomplete**.
3. **Collect clauses** from every licence along every path (including every parent of a merge).
4. **Apply**: any applicable BLOCK -> **BLOCKED**. Otherwise, if lineage is incomplete, or any licence on the path is `unknown` or `other`, or any applicable clause is NEEDS_COUNSEL -> **CANNOT_DETERMINE** (list why). Otherwise, if applicable obligations exist -> **ALLOWED_WITH_OBLIGATIONS**. Else **ALLOWED**.
5. **Declared-differs flag**: if the queried model's declared licence is more permissive than an inherited licence, add `declared_differs: true` with both licence names.
6. **Alternatives** (only when BLOCKED): evaluate up to 8 models from `data/alternatives.json` with the same `pipeline_tag`; return the ones that come out ALLOWED or ALLOWED_WITH_OBLIGATIONS. If none, say "no compliant alternative in our candidate set" (scope it honestly; never claim none exists anywhere).
7. **Explanation**: evidence list of `{path, licence, clause id, quote, source_url}`; LLM phrases it if available, otherwise use a template.

Verdict response (also the MCP `can_i_use` payload):
```json
{
  "model_id": "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
  "verdict": "BLOCKED",
  "strict": false,
  "declared_license": "apache-2.0",
  "declared_differs": true,
  "inherited_licenses": ["llama3_2"],
  "blocking": [{"clause_id":"llama3_2.geo_eu_multimodal","quote":"...","source_url":"...","section":"...",
                 "path":["OPEA/Llama-3.2V-11B-cot-int4-sym-inc","Xkev/Llama-3.2V-11B-cot","meta-llama/Llama-3.2-11B-Vision-Instruct"],
                 "edge_tiers":[2,2]}],
  "obligations": [{"clause_id":"llama3_2.name_prefix","status":"NOT_SATISFIED"}],
  "lineage_complete": true,
  "alternatives": [],
  "ruling_id": "rul_...",
  "explanation": "...",
  "disclaimer": "Automated screening, not legal advice."
}
```

### 6.3 Hidden-lineage resolver
1. For each ingested model, write fingerprints:
   - `weights_sha256`: `lfs.sha256` of every `*.safetensors` and `*.bin` file (one Fingerprint per file).
   - `tokenizer_sha`: `blobId` (or `lfs.sha256`) of `tokenizer.json`, else `tokenizer.model`.
   - `config_fp`: sha256 of canonical JSON of these `config.json` keys: `architectures, model_type, hidden_size, intermediate_size, num_hidden_layers, num_attention_heads, num_key_value_heads, vocab_size, max_position_embeddings, rope_theta, rope_scaling`. Skip if `config.json` is not fetchable.
   - `vocab_dna`: sha256 prefix of the token vocabulary (see F20 and `docs/ADDENDUM_WEIGHT_DNA.md` section 5.3); joins the same WCC resolver (R1) but alone never creates an edge.
2. Run `CALL algo.WCC({nodeLabels:['Model','Fingerprint'], relationshipTypes:['HAS_FP']}) YIELD node, componentId` and group models by component.
3. For a model with **no declared parent** inside a component that contains a root model:
   - shares a `weights_sha256` with the root -> edge `relation: mirror, conf: 0.97, tier: 1`
   - shares `tokenizer_sha` **and** `config_fp` -> `relation: inferred, conf: 0.8, tier: 1`
   - shares only `config_fp` -> `relation: inferred, conf: 0.5, tier: 0`
   - pick the parent: the root in the component with the same `config_fp`; tie-break by earliest `created_at`.
4. Never overwrite a declared edge with an inferred one. Write `evidence` naming the shared fingerprint keys.
5. **Weight DNA resolver (F20):** after step 4, for each model with `dna_status = 'OK'`, `dna_reference` not true, and no `weights` / `weights_merge` edge yet, run W2–W3 (single parent) or merge fit + W7. Foundation models in `data/dna_references.json` are fingerprinted with `dna_reference = true` and are **never** candidates in W2/W7 (do not use `is_root` for this). Never overwrite a declared edge; if weights point to a different family than the declared parent, keep both edges (W5 lists conflicts). Vector index W0 lives only on `hub`.
6. **Canonical ids:** always key `Model.id` by the `id` field that `GET /api/models/{id}` returns. When a declared `base_model` or a requested id differs (Hub redirect), write edges to the canonical node and append the requested id to `Model.aliases`. Verdict and MCP tools accept aliases (`id` or `$id IN m.aliases`).

### 6.4 Reverse fan-out and reopen
Triggered by the Watcher when a hub model's `sha` changes (or when an edge tier changes):
1. Snapshot the new revision (`Snapshot` node), re-parse card, licence, base_model, files; update `Model` properties; write `DECLARES` with the new `as_of_sha`.
2. Diff: licence changed, licence file added, notice added, base_model changed.
3. Descendants: D1 returns every descendant id (bounded *1..6).
4. For each tenant graph (`GRAPH.LIST` or our registry of tenant graph names): T3 finds active rulings whose `Fact.model_id` is in `{changed} + descendants`. For each: create `Event {kind: REOPENED, reason}`, create `Task {kind: REVIEW_RULING}` assigned to the deployment owner, have the Auditor recompute and write a **new** ruling that `SUPERSEDES` the old one once the owner approves.
5. Publish a fan-out summary to the UI (counts per tenant, list of descendants that did not inherit the fix: "fix leverage").

### 6.5 Compounding (Publisher)
- `POST /api/tenants/{t}/confirm` with `{child, parent}` records `Event {kind: CONFIRMED_EDGE}` in the tenant and calls the Publisher.
- Publisher adds the salted tenant hash to `DERIVED_FROM.confirmers` in the hub (create the edge at tier 1 if it did not exist), sets `confirmations = size(confirmers)`, and promotes to tier 3 when `confirmations >= 2`.
- Any tenant's next verdict (including strict mode) sees the higher tier. This is the demo's shot 3: company A confirms, company B's strict verdict flips from CANNOT_DETERMINE to BLOCKED.

### 6.6 The real-world loop (Notifier)
- When `declared_differs` is true for a hub model, the Notifier drafts a short, polite Hub discussion ("The card declares apache-2.0; its base model is under the Llama 3.2 Community License, which asks derivatives to ...; would you consider adding ..."). LLM-phrased if available, template otherwise.
- The draft becomes a `Task {kind: APPROVE_POST}`. Approve posts only if the repo is in `HF_POST_ALLOWLIST`; otherwise the UI offers "copy draft".
- Live loop demo: our own test repo (README + config only, declares `base_model: meta-llama/Llama-3.2-1B` and `license: apache-2.0`). Post the discussion, edit the card to declare `llama3.2`, and the Watcher (or a manual "check now" button) picks up the new sha, promotes the edge to tier 4, and reopens dependent rulings.
- Replay demo: the Xkev history from its real commits (before and after 2025-11-16) and discussion 12.

### 6.7 Agents and handoffs
Agents are deterministic workers with narrow tools; they hand work to each other through `Task` nodes in the tenant graph (Track 2).
| Agent | Does | Tools |
|---|---|---|
| Scout | ingests models, children, files, commits into the hub | HF client, hub writes (MERGE) |
| Resolver | fingerprints, WCC, inferred edges | hub reads/writes, `algo.WCC` |
| Auditor | computes verdicts and writes rulings | Q1, clause engine, tenant writes |
| Watcher | polls shas of watched models every 10 min; triggers fan-out | HF client, D1, T3, T4 |
| Notifier | drafts discussions and owner notices | LLM (optional), Draft nodes |
| Publisher | promotes hub edges from tenant confirmations | hub writes |
Task protocol (full detail in FLOWS F9): OPEN -> CLAIMED (with `lease_until` = now + 2 min) -> AWAITING_APPROVAL -> DONE; a stale lease returns to OPEN; every transition is an `Event`. Writes use MERGE on ids (idempotent). Concurrent ruling writes on the same deployment: compare the client's `expected_ruling_id`; if it is not the latest, return HTTP 409.

---

## 7. API (FastAPI, `services/api`)

Summary only. **`docs/API.md` is the authoritative contract** (types, errors, every endpoint; model paths are `/api/models/{owner}/{name}/...`).


| Method and path | Body or query | Returns |
|---|---|---|
| `GET /api/health` | | `{falkordb:"up", graphs:[...], hf:"ok"}` |
| `POST /api/verdict` | `{model_id, context, tenant?, product_id?, strict?}` | verdict JSON (section 6.2); writes a ruling if a tenant is given |
| `GET /api/models/{id}/lineage` | `?depth=6&min_tier=1` | nodes and edges for the graph view |
| `GET /api/models/{id}/descendants` | `?depth=2&limit=200` | descendants with declared licences (fan-out view) |
| `POST /api/ingest` | `{model_id, children?: bool}` | `{job_id}`; `GET /api/jobs/{id}` and `GET /api/jobs/{id}/events` (SSE) |
| `POST /api/sandbox` | | creates `sbx_<id>` from a tenant template; returns `{tenant, token, expires_at}` |
| `GET /api/tenants/{t}/overview` | | company, teams, products, deployments, latest ruling per deployment |
| `POST /api/tenants/{t}/confirm` | `{child, parent}` | tier change, flip summary |
| `GET /api/tenants/{t}/tasks` | | open tasks |
| `POST /api/tasks/{id}/claim`, `/approve`, `/reject` | `{person_id}` | event; approve on APPROVE_POST posts only if allowlisted |
| `POST /api/watch/check` | `{model_id}` | runs the watcher now for one model (demo button) |
| `GET /api/replay/xkev` | | timeline: commits, discussion, card states, children states |
| `POST /api/ci/check` | `{repo, models:[...], context}` | `{pass: bool, results:[verdicts]}` |
| `GET /api/eval` | | latest eval report JSON |

Public access: read endpoints and `/api/verdict` without tenant are open; tenant writes need the sandbox token (visitors) or `ADMIN_TOKEN` (us). Visitors can never write to `tenant_kestrel` or `tenant_harbor` directly; they get a sandbox copy.

Abuse limits (slowapi): verdict 30/min/IP, ingest 6/10 min/IP, sandbox 3/hour/IP; ingest refuses more than 300 nodes; LLM calls capped per IP per day and by a global daily budget; HF calls go through one shared limiter.

---

## 8. MCP server (`/mcp`, streamable HTTP)

Tools (names exactly as below; descriptions written for a coding agent):
| Tool | Arguments | Returns |
|---|---|---|
| `can_i_use` | `model_id` (str), `hq_country` (ISO-2), `commercial` (bool, default true), `markets` (list, optional), `mau` (int, optional), `tenant` + `token` (optional), `strict` (bool, default false) | verdict summary + `ruling_id` + link to the explanation page |
| `explain` | `model_id` or `ruling_id` | paths, clauses with quotes, edge tiers, what would change the answer |
| `lineage` | `model_id`, `depth` | ancestors and descendants with licences and tiers |
| `proof_path` | `model_id`, `root_id` | shortest derivation path (A4) or proof that none exists |
| `relabel_hubs` | none | PageRank-ranked models whose declared licence differs from inherited (A1) |
| `chokepoints` | none | betweenness-ranked models (A2) |
| `families` | none | community detection over lineage (A3) |
| `watch` | `model_id`, `tenant`, `token` | subscribes the tenant; future upstream changes create tasks |
| `confirm_edge` | `child`, `parent`, `tenant`, `token` | publisher result |

Connect from Claude Code (document in README):
```bash
claude mcp add --transport http modelbrain https://<api-host>/mcp
```
Demo prompt: "Before you add `from_pretrained("OPEA/Llama-3.2V-11B-cot-int4-sym-inc")` for our Berlin company's commercial product, check with modelbrain."

---

## 9. GitHub Action (`actions/modelbrain-check`)
- `action.yml` (composite). Inputs: `api_url`, `hq_country`, `commercial`, `markets`, `strict`.
- Scans `**/*.py` and `**/*.ipynb` for `from_pretrained("...")`, `pipeline(..., model="...")`, `hf_hub_download(repo_id="...")`, `snapshot_download(repo_id="...")`, and reads optional `modelbrain.yml` (explicit model list and context).
- Calls `POST /api/ci/check`; writes a table to `$GITHUB_STEP_SUMMARY`; exits 1 on any BLOCKED (and on CANNOT_DETERMINE when `strict: true`).
- Demo repo `modelbrain-demo-app` (ours) with a PR that adds the OPEA model -> red check; a second PR switching to an allowed model -> green.
- If time runs short, cut the Action before the MCP server (see cut order).

---

## 10. Web app (`apps/web`, Next.js on Vercel)

Summary only. **`docs/UI.md` is the authoritative page, state and copy specification.**


Pages
1. `/` Hero: "Can you ship this model?" Input: model id (with examples as chips: OPEA/Llama-3.2V-11B-cot-int4-sym-inc, SicariusSicariiStuff/Llama-3.2-1B_Base_FP8, grimjim/llama-3-Nephilim-v1-8B, Qwen/Qwen2.5-7B-Instruct). Context controls: HQ country (default DE), commercial toggle, markets, MAU, strict mode toggle.
2. `/m/[...id]` Verdict: big badge (green ALLOWED, amber ALLOWED WITH OBLIGATIONS, red BLOCKED, grey CANNOT DETERMINE), "declared vs inherited" strip, the path drawn as a graph with edge tiers (solid declared, dashed inferred, gold confirmed), clause cards with verbatim quotes and source links, obligations checklist, alternatives, "explain like a lawyer would ask" section, and the Cypher that produced it (collapsible).
3. `/companies` Two columns: Kestrel Analytics GmbH (fictional, DE) and Harbor Apps Inc. (fictional, US): products, deployments, latest ruling, open tasks, events timeline. "Try it in your own sandbox" button.
4. `/hidden-lineage` WCC components, Confirm buttons, relabel hubs (PageRank), chokepoints (betweenness), families (label propagation).
5. `/replay/xkev` Timeline scrubber over the real Xkev history; the fan-out view lights the 9 children; "fix leverage" counter.
6. `/live-loop` Our test repo: draft, approve, post, "check now", reopened rulings.
7. `/mcp` How to connect Claude Code and Cursor; copyable command; tool list.
8. `/eval` Frozen eval results vs baselines, with the labels hash.
9. `/how-it-works` Graph model diagram, the queries, the tiers, privacy rule.

Design: dark-neutral background, one accent; verdict colours are semantic (green, amber, red, grey). Every verdict page shows the disclaimer.

---

## 11. Demo tenants (fictional, `data/demo_tenants/`)
- **Kestrel Analytics GmbH (fictional)**, HQ DE, EU, MAU 120k. Team "Claims AI" owns product "Claims Vision Assistant" (commercial, markets DE/FR/NL) with deployment `OPEA/Llama-3.2V-11B-cot-int4-sym-inc`. Team "Support" owns "Support Copilot" with deployment `SicariusSicariiStuff/Llama-3.2-1B_Base_FP8`. People: Lena Vogt (owner, Claims AI), Jonas Brandt (legal), Mira Haas (engineer). All fictional.
- **Harbor Apps Inc. (fictional)**, HQ US, MAU 2M. Team "Mobile" owns "Photo Notes" (commercial, US) with a deployment on one of Xkev's children; Team "Platform" owns "Ticket Triage" with `shuyuej/Llama-3.2-1B-GPTQ`. People: Dana Ortiz (owner), Sam Lee (legal), Priya Nair (engineer). All fictional.
- Pre-seed one active ruling per deployment so the reopen and flip demos have something to change.

---

## 12. Frozen eval (`eval/`)
- `eval/models.csv`: 40 models chosen before rule code is written: 10 Llama 3.2 Vision descendants, 8 Llama 3.1/3.2 text descendants including relabels, 6 Gemma descendants (including the SimPO relabel hub), 6 Qwen/Mistral apache models, 5 merges (including Nephilim), 5 parentless re-uploads (the 3 verified ones plus 2 more found by search).
- Two contexts each: `EU_COMMERCIAL` (DE, commercial) and `US_COMMERCIAL` (US, commercial, MAU 2M) = 80 labelled verdicts.
- Teammate B labels `eval/labels.json` by reading licences and cards **before** teammate A writes clause rules. Commit `eval/labels.sha256` and put the hash in the README.
- Metrics: verdict accuracy; **false ALLOW count (target 0)**; CANNOT_DETERMINE rate (honest unknowns); `declared_differs` precision and recall; strict vs default.
- Baselines: (a) declared-licence-only rules (what a card scanner does); (b) card-only LLMs via OpenRouter (each model in `EVAL_BASELINE_MODELS` given only the model card). Show both on `/eval`. This is the answer to "is the graph decoration?".

---

## 13. Repo layout
```
modelbrain/
  AGENTS.md  BLUEPRINT.md  README.md  docker-compose.yml  .env.example
  .cursor/rules/modelbrain.mdc
  docs/TASKS.md  docs/queries.cypher
  data/clauses.seed.json  data/eu_countries.json  data/alternatives.json  data/roots.json
  data/demo_tenants/kestrel.cypher  data/demo_tenants/harbor.cypher
  services/api/
    pyproject.toml  Dockerfile
    app/main.py  app/config.py
    app/hf/client.py  app/hf/parse.py  app/hf/cache.py
    app/graph/db.py  app/graph/queries.py  app/graph/schema.py
    app/engine/clauses.py  app/engine/verdict.py  app/engine/resolver.py  app/engine/fanout.py  app/engine/publisher.py
    app/agents/scout.py  app/agents/auditor.py  app/agents/watcher.py  app/agents/notifier.py  app/agents/tasks.py
    app/mcp_server.py
    app/routes/verdict.py  app/routes/models.py  app/routes/tenants.py  app/routes/ci.py  app/routes/replay.py  app/routes/eval.py
    tests/  (fixtures: tiny hub graph; golden verdicts)
  apps/web/  (Next.js)
  actions/modelbrain-check/action.yml  actions/modelbrain-check/check.py
  eval/models.csv  eval/labels.json  eval/labels.sha256  eval/run_eval.py  eval/baseline_card_only.py  eval/report.json
```

---

## 14. Build plan (about 22 hours, two people plus Cursor)
H0 is the moment work starts. Person A: backend and graph. Person B: frontend, eval, video. Details and acceptance criteria are in `docs/TASKS.md`.

| Hours | Person A | Person B | Milestone |
|---|---|---|---|
| 0-1 | scaffold, docker-compose, Railway FalkorDB + API, schema and indexes | Vercel project, Next.js shell, design tokens | both deploy "hello" |
| 1-4 | HF client + cache + parse; Scout ingest of ancestry; Q1 | eval model list, then **labels** (before rules exist) | `/api/models/{id}/lineage` live |
| 4-8 | Clause Loader (runtime quote extraction), evaluator, verdict API, explanation template | home + verdict page + lineage graph wired to API | **H8: public URL answers BLOCKED for OPEA in DE, ALLOWED WITH OBLIGATIONS in US, with path and quotes** |
| 8-12 | tenants, sandbox, rulings, tasks; MCP server | tenants page, MCP page; record Claude Code calling `can_i_use` | MCP works from Claude Code |
| 12-16 | fingerprints, WCC resolver, inferred edges, strict mode, Publisher | eval runner + both baselines; `/eval` page | parentless re-upload unmasked; A confirms, B flips |
| 16-19 | Watcher, fan-out, reopen, Xkev replay, live loop on our test repo | replay page, live-loop page, fan-out visual | all three demo shots work end to end |
| 19-21 | rate limits, caches, prewarm demo set, tests green, GitHub Action | polish, empty and error states, mobile check | stable deployment |
| 21-23 | README: data model, Cypher, setup, tracks, AI disclosure | 3-minute video, blog post draft (side prize) | submission assets ready |
| 23-24 | buffer, submit | buffer | submitted |

**Cut order if behind** (cut from the top, never touch the H8 core): 1) GitHub Action fallback snapshot; 2) GitHub Action; 3) live posting loop (keep the Xkev replay); 4) sandbox copies (use the two fixed tenants, read-only for visitors); 5) LLM explanations (templates); 6) `/how-it-works` page (move content into README).

**M6b cut order** (after add-ons in section 18, before core): G152 (merges/GGUF on `/findings`; keep verdict chips), G153 crawl size (fall back to prewarm + 500 models + 100 GGUF), G149 live GGUF check, G150 merge. **G140–G142, G145, G147 and G148 are not cuttable once started.**

---

## 15. The 3-minute video
| Time | Shot | Track |
|---|---|---|
| 0:00-0:15 | Cold open: "This model card says apache-2.0. Its weights say Llama. A Berlin company may not use it at all." | hook |
| 0:15-1:00 | Claude Code adds `from_pretrained("OPEA/...")`, calls `can_i_use` over MCP, gets BLOCKED with the path and quote; the demo PR goes red; flip HQ to US -> amber, allowed with obligations | T1 |
| 1:00-1:40 | Paste a parentless re-upload: CANNOT DETERMINE in strict mode; the resolver shows the identical tokenizer and config hashes (WCC component) | T1 |
| 1:40-2:15 | Two tenant graphs side by side: Kestrel confirms the edge; Harbor's strict verdict flips; Publisher shows tier 1 -> 3, and no tenant identity in the hub | T2 |
| 2:15-2:40 | Xkev replay: the fix lands upstream after 130 days; the 9 children light up; rulings reopen and become tasks for named (fictional) owners | T2 + T3 |
| 2:40-2:55 | Eval: 80 frozen verdicts, false ALLOW 0, beats card-only scanner and card-only LLM | proof |
| 2:55-3:00 | Live URL, MCP command, "Automated screening, not legal advice." | close |

---

## 16. Risks and answers
| Risk | Answer |
|---|---|
| "The verdict is just an ancestor walk" | Merges (multi-parent DAG 10+ levels), inferred edges via WCC, tiered trust, reverse fan-out across tenants, and the eval vs card-only baselines |
| "Provenance is crowded" | We are not lineage: we evaluate inherited obligations against a company's context and keep rulings current. Zero FalkorDB entries in this space; mlabonne's Model Family Tree colours ancestry by licence but has no obligations, context, memory or MCP |
| Hub rate limits during judging | token, cache, prewarmed demo set, per-IP limits, graceful "queued" UI |
| Gated repos | metadata and hashes are public; fetch configs from non-gated mirrors or with a token that accepted the gate |
| Legal wording | section 2.5 wording; disclaimer; no posting to third parties |
| Synthetic companies look thin | they are labelled; the hub is real; the sandbox lets judges act as a company |
| Scope | the cut order in section 14 |

---

## 16.5 Decided on 18 Oct 2026 (do not revisit)
- Add-ons in section 18 are decided; their cut order is in section 18.
- Product: ModelBrain v3. Primary Track 1; also Tracks 2 and 3.
- Hosting: Vercel (web) + Railway (API and FalkorDB in Docker). Not FalkorDB Cloud free tier.
- MCP SDK pinned below 2.0.
- Licence text is never stored in the repo; quotes are extracted at runtime from official sources by locators verified on 18 Oct (33 of 34 clauses resolve; OpenRAIL is NEEDS_COUNSEL by design).
- Llama 4: the EU exclusion for multimodal models is present in its Acceptable Use Policy (verified 18 Oct).
- Repository licence: MIT (team to confirm ownership per rule 15).

## 17. Submission checklist
- [ ] Live URL (Vercel) and API (Railway) up; `/api/health` green.
- [ ] Public repo with README: setup, graph data model (sections 5.1 and 5.2), Cypher queries (link `docs/queries.cypher`), algorithms used (`algo.WCC`, bounded variable-length paths), MCP connect command, tracks (T1 primary; T2, T3), AI coding assistant disclosure.
- [ ] Demo video (3 minutes) linked in README and the submission form.
- [ ] `eval/labels.sha256` committed and quoted in README; `/eval` shows results.
- [ ] Blog post (side prize) drafted from the README story.
- [ ] Everyone can explain the graph model, the queries (Q1, Q2, R1, D1, P1, T3, A1-A4), tiers and the privacy rule (`docs/EXPLAINER.md`).
- [ ] LICENSE file added and ownership agreed (rule 15).
- [ ] Every goal in `docs/GOALS.md` marked done or explicitly cut with a reason.

## 18. Add-ons (decided 18 Oct 2026)
Each add-on was accepted only if it strengthens the graph or the proof, not just the surface. All are built after milestone M6 except the LLM gateway, and all are cuttable before any core goal.

| Add-on | Decision | What it adds to the graph | Why |
|---|---|---|---|
| **OpenRouter as the single LLM gateway** | Accept (Block 2) | nothing; replaces the Anthropic-only client | one key, any model; explanations and drafts stay LLM-optional |
| **Multi-LLM card-only baseline** | Accept (Block 4) | none | the eval shows the graph beats several frontier LLMs that read only the model card: the strongest answer to "is the graph decoration?" |
| **Hosted path (OpenRouter catalogue)** | Accept (after M6) | `Provider {hq, datacenters, tos_url}`, `HostedModel`, `(HostedModel)-[:IS]->(Model)`, `(Provider)-[:SERVES {quantization, uptime}]->(HostedModel)` (queries O1-O5) | most companies call models through an API, not weights. Real public data: 180 of 470 OpenRouter models carry a `hugging_face_id`; 112 providers publish headquarters and datacenter countries. New proof: "no provider serves this model from an EU datacenter" (O4 returns no rows) |
| **Licence text watch** | Accept (after M6) | `LicenseText {url, sha, fetched_at}` versions, `(Clause)-[:FROM_TEXT]->(LicenseText)` (L1, L2); tenant query T8 | when Meta, Google or a provider changes a licence, use policy or terms page, every ruling resting on an affected clause reopens: knowledge kept current at the legal-text level |
| **Web fetcher adapter (Firecrawl or Anakin)** | Accept as optional backend | none | plain HTTP already resolves 33 of 34 clause sources; the adapter handles JavaScript-heavy or custom licence pages linked from model cards (`cardData.license_link`) and can use the provider's change-tracking for the text watch. `WEB_FETCHER=httpx` (default), `firecrawl` or `anakin` |
| **Custom licence resolution** | Accept (after M6) | `Model.license_text_sha`, `(Model)-[:DECLARES {source:"matched_text"}]->(License)` | models declaring `other` with a `license_link`: fetch the text, compare its normalised sha and distinctive phrases with known licence texts; a match becomes a declared licence, anything else stays NEEDS_COUNSEL. Lowers the CANNOT_DETERMINE rate without guessing |
| ~~Ask the company brain (natural language)~~ | **Cut 18 Oct 2026** (was G079/G135/G136) | — | funded M6b weight DNA |
| ~~Voice~~ | **Cut 18 Oct 2026** (was G137) | — | funded M6b weight DNA |
| **Weight DNA (M6b)** | Accept (after M5, before other add-ons except G126) | `Model.dna` vector index (W0), weight/merge edges, GGUF header facts, exposure (W8) | provenance from sampled weight values, not only the model card; see `docs/ADDENDUM_WEIGHT_DNA.md` |

Cut order for add-ons (cut these before anything in section 14): voice and Ask (already cut), custom licence resolution, web fetcher adapter (keep plain HTTP), licence text watch, hosted path, multi-LLM baseline (keep the declared-licence baseline). The OpenRouter gateway is part of the core because the explanation code uses it.
