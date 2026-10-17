# ModelBrain API contract

Base URL: `https://<api-host>` (Railway). All JSON. Times are ISO-8601 UTC strings in responses, epoch ms inside the graph. This file is the contract between `services/api`, `apps/web`, the MCP server and the GitHub Action; change it here first.

## Conventions
- Auth headers: `X-Tenant-Token` (sandbox token from `POST /api/sandbox`) or `Authorization: Bearer <ADMIN_TOKEN>`.
- Request id: every response has header `X-Request-Id`; log lines carry it.
- Error envelope (all non-2xx):
```json
{ "error": { "code": "MODEL_NOT_FOUND", "message": "No model 'foo/bar' on the Hugging Face Hub.", "hint": "Check the id, e.g. meta-llama/Llama-3.2-1B.", "retry_after_s": null } }
```
- Error codes: `INVALID_INPUT` 422, `MODEL_NOT_FOUND` 404, `UNAUTHORIZED` 401, `SANDBOX_EXPIRED` 401, `READ_ONLY_TENANT` 403, `NOT_ALLOWLISTED` 403, `STALE_RULING` 409, `RATE_LIMITED` 429, `GRAPH_UNAVAILABLE` 503, `HUB_UNAVAILABLE` 503, `INTERNAL` 500.
- Rate limits (per IP): verdict 30/min, ingest 6/10 min, sandbox 3/h, everything else 120/min. 429 responses include `retry_after_s`.

## Shared types
```ts
type Context = {
  hq_country: string            // ISO-2, e.g. "DE"
  markets?: string[]            // ISO-2 list, default [hq_country]
  commercial?: boolean          // default true
  mau?: number                  // default 0
  distributes_weights?: boolean // default false
  end_user_only?: boolean       // default false
}
type VerdictKind = "ALLOWED" | "ALLOWED_WITH_OBLIGATIONS" | "BLOCKED" | "CANNOT_DETERMINE"
type ClauseHit = {
  clause_id: string; kind: string; effect: "BLOCK" | "OBLIGATION" | "NEEDS_COUNSEL"
  license: string; quote: string | null; summary: string; source_url: string; section: string
  path: string[]                // model ids from the queried model to the licence carrier
  edge_tiers: number[]; relations: string[]
  status?: "SATISFIED" | "NOT_SATISFIED" | "NOT_CHECKABLE"   // obligations only
}
type Verdict = {
  model_id: string; verdict: VerdictKind; strict: boolean; context: Context
  declared_license: string | null; declared_differs: boolean; inherited_licenses: string[]
  blocking: ClauseHit[]; obligations: ClauseHit[]; needs_counsel: ClauseHit[]
  lineage_complete: boolean; incomplete_reasons: string[]
  alternatives: { model_id: string; verdict: VerdictKind }[]
  paths: { path: string[]; tiers: number[]; relations: string[] }[]
  explanation: string; explanation_source: "llm" | "template"
  cypher: { q1: string; q2: string }
  ruling_id: string | null; stale: boolean
  disclaimer: "Automated screening, not legal advice."
  computed_ms: number
}
type Queued = { status: "QUEUED"; job_id: string; events_url: string }
```

## Endpoints

### Health and admin
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/health` | none | `{ok, falkordb:"up"|"down", graphs:string[], hub_models:number, clauses:{resolved,unresolved}, hf:"ok"|"degraded", version}` |
| GET | `/api/admin/resolver/last` | admin | last resolver report |
| POST | `/api/admin/reload-clauses` | admin | clause loader report |

### Models and verdicts
| Method | Path | Body / query | Response |
|---|---|---|---|
| POST | `/api/verdict` | `{model_id, context, strict?, tenant?, deployment_id?, expected_ruling_id?}` | 200 `Verdict` or 202 `Queued` |
| GET | `/api/models/{owner}/{name}` | | hub model properties + declared licence + snapshot count |
| GET | `/api/models/{owner}/{name}/lineage` | `depth=6`, `min_tier=1` | `{nodes:[{id, declared_license, is_root, multimodal}], edges:[{child,parent,relation,source,tier,conf,evidence}]}` |
| GET | `/api/models/{owner}/{name}/descendants` | `depth=2`, `limit=200` | `{descendants:[{id, declared_license, card_has_llama_notice, has_license_file}], fix_leverage:{descendants, not_inherited}}` |
| GET | `/api/models/{owner}/{name}/proof-path` | `root_id` | `{no_path, path, hops}` (A4) |
| POST | `/api/ingest` | `{model_id, children?}` | 202 `{job_id, events_url}` |
| GET | `/api/jobs/{job_id}` | | `{status:"running"|"done"|"failed", nodes, error?}` |
| GET | `/api/jobs/{job_id}/events` | | SSE stream of `{type:"started"|"node"|"done"|"error", ...}` |

### Graph algorithms (also MCP tools)
| Method | Path | Response |
|---|---|---|
| GET | `/api/algo/relabel-hubs` | `[{model, score}]` (A1 PageRank, top 20) |
| GET | `/api/algo/chokepoints` | `[{model, score}]` (A2 betweenness, top 20) |
| GET | `/api/algo/families` | `[{community_id, size, sample}]` (A3 label propagation) |
| GET | `/api/algo/hidden-lineage` | `[{component_id, model_ids, inferred_edges:[...]}]` (R1 + R3 results) |

### Tenants, memory and tasks
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/api/sandbox` | none | `{template:"kestrel"|"harbor"}` | `{tenant, token, expires_at}` |
| GET | `/api/tenants` | none | | `[{name, company, hq_country, kind:"fixed"|"sandbox"}]` (fixed tenants + caller's sandbox) |
| GET | `/api/tenants/{t}/overview` | read: none for fixed, token for sandbox | | `{company, teams, people, products:[{id,name,deployments:[{id, model_id, owner, latest_ruling:{id, verdict, decided_at}}]}]}` (T6) |
| GET | `/api/tenants/{t}/rulings/{ruling_id}/trace` | same | | T7 decision trace |
| GET | `/api/tenants/{t}/events` | same | `limit=50` | events newest first |
| POST | `/api/tenants/{t}/confirm` | token/admin | `{child, parent, person_id}` | `{tier_before, tier_after, confirmations, reopened:[ruling_id]}` |
| GET | `/api/tenants/{t}/tasks` | token/admin | `state=OPEN|CLAIMED|AWAITING_APPROVAL|DONE` | tasks |
| POST | `/api/tasks/{task_id}/claim` | token/admin | `{agent \| person_id}` | `{claimed: bool}` |
| POST | `/api/tasks/{task_id}/approve` | token/admin | `{person_id}` | `{ruling_id?, posted_url?, ready_to_copy?}` |
| POST | `/api/tasks/{task_id}/reject` | token/admin | `{person_id, reason}` | `{ok}` |
| GET | `/api/tenants/{t}/conversations` | token/admin | | `[{id, started_at, turns}]` |

### Watcher, replay, loop
| Method | Path | Auth | Response |
|---|---|---|---|
| POST | `/api/watch/check` | admin, or token for models in the caller's sandbox | `{changed: bool, diff:{license_changed, license_file_added, notice_added, parents_changed}, fanout:{descendants, tenants:{name:count}}}` |
| GET | `/api/replay/xkev` | none | `{events:[{at, kind:"commit"|"discussion"|"fix", title, sha?, url}], children:[{id, declared_license, notice, license_file}], fix_leverage:{descendants, not_inherited}}` |
| POST | `/api/drafts` | token/admin | `{model_id}` -> `{draft_id, title, body, target_repo, task_id, allowlisted}` |

### CI and eval
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/ci/check` | `{repo, models:string[], context, strict?}` | `{pass, results: Verdict[]}` |
| GET | `/api/eval` | | `eval/report.json` |

## MCP tools (`/mcp`, streamable HTTP)
Descriptions are written for the calling agent; keep them as below.

| Tool | Description (verbatim in code) | Input schema | Output |
|---|---|---|---|
| `can_i_use` | "Check whether a Hugging Face model may be used in a product, given where the company is based and how the product is used. Call this before adding from_pretrained or downloading a model." | `{model_id: string, hq_country: string, commercial?: boolean, markets?: string[], mau?: integer, distributes_weights?: boolean, strict?: boolean, tenant?: string, token?: string}` | text summary + structured `Verdict` |
| `explain` | "Explain a verdict: every ancestry path, the licence clauses with quotes and sources, trust tiers, and what would change the answer." | `{model_id?: string, ruling_id?: string, hq_country?: string}` | text + structured |
| `lineage` | "Return a model's ancestors and descendants with declared licences and trust tiers." | `{model_id: string, depth?: integer}` | structured |
| `proof_path` | "Shortest derivation path from a model to a given base model, or proof that none exists." | `{model_id: string, root_id: string}` | `{no_path, path, hops}` |
| `relabel_hubs` | "Models whose declared licence differs from what they inherit, ranked by PageRank influence over their descendants." | `{}` | `[{model, score}]` |
| `chokepoints` | "Models with the highest betweenness in the lineage graph: fixing one reaches the most descendants." | `{}` | `[{model, score}]` |
| `families` | "Model families found by community detection over lineage." | `{}` | `[{community_id, size, sample}]` |
| `watch` | "Subscribe a tenant to upstream changes for a model; changes reopen dependent rulings." | `{model_id, tenant, token}` | `{watching: true}` |
| `confirm_edge` | "Confirm that a model derives from a parent. Two independent confirmations raise the edge's trust tier for everyone." | `{child, parent, tenant, token, person_id}` | publisher result |

Every MCP call writes a `(:Turn {tool, args_json, verdict, at})` to the tenant's `(:Conversation)` when a tenant is given (persistent conversation history, Track 2).

## Add-on endpoints (BLUEPRINT section 18)
| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/api/hosted` | `q` (search), `limit=50` | `[{or_id, name, hf_id}]` from the hub |
| GET | `/api/hosted/{author}/{slug}/providers` | `residency=EU` or `countries=DE,FR` | `{providers:[{provider, name, hq, datacenters, quantization, uptime}], residency_ok}` (O4) |
| POST | `/api/verdict` | additionally accepts `hosted_model_id` and `context.data_residency` | `Verdict` + `hosted` block (FLOWS F16) |
| POST | `/api/tenants/{t}/ask` | `{question}` | `{template, params, rows, cypher, sources, answer_text}` (FLOWS F18) |
| POST | `/api/admin/licence-watch/run` | | `{checked, changed:[url], reopened:{tenant: count}}` (FLOWS F17) |

Additional `Context` field: `data_residency?: "EU" | string[]`.

Additional MCP tools:
| Tool | Description (verbatim in code) | Input | Output |
|---|---|---|---|
| `where_can_i_run` | "List inference providers that serve a hosted model from allowed datacenter countries, or prove that none do." | `{hosted_model_id: string, residency: string \| string[]}` | providers + `residency_ok` |
| `ask_company` | "Answer a question about how a company uses AI models (owners, deployments, reopened rulings, signatures) from its graph, with sources." | `{tenant, token, question}` | answer + Cypher + sources |
