# AGENTS.md: rules for every coding agent working on ModelBrain

Read `BLUEPRINT.md` section 0 (document map) before writing code. The binding documents are AGENTS.md, BLUEPRINT.md, docs/GOALS.md, docs/FLOWS.md, docs/API.md, docs/UI.md, docs/queries.cypher and docs/REQUIREMENTS.md; this file is the short list of rules. When the spec and your instinct disagree, follow the spec and leave a note in `docs/TASKS.md` under "Questions for the owner".

## Deadline and priorities
- Submissions close Sunday 18 Oct 2026, 11:59 PM IST. Work through `docs/GOALS.md` top to bottom (138 goals with acceptance tests); `docs/TASKS.md` is the hour-by-hour summary. Do not stop until every goal is done or explicitly struck through with a reason.
- The hour-8 core (paste a model id, get a verdict with path and quoted clause, deployed) must never break. Every later feature is additive.
- If you are behind, cut in the order listed in BLUEPRINT.md section 14. Never cut the core, the README requirements or the eval.

## Product rules (do not break)
1. Verdicts come from FalkorDB traversals (`docs/queries.cypher`). Do not compute ancestry in Python and only mirror it into the graph.
2. Deterministic code decides. An LLM may only phrase explanations from evidence it is given, or draft discussion text. With no LLM key set, templates are used and everything still works.
3. No outward action without an Approve click by an authenticated human. Never post to a Hugging Face repo that is not in `HF_POST_ALLOWLIST`.
4. Rulings, confirmations, approvals and snapshots are append-only. A changed answer is a new ruling that supersedes the old one.
5. Wording: "declared licence differs from inherited obligations", "may not be permitted", "needs counsel". Never "violating", "illegal" or anything accusing a named person or company. Every verdict shows "Automated screening, not legal advice."
6. Never paste licence text into the repo. The Clause Loader (`docs/FLOWS.md` F3) extracts each quote at runtime from `source_raw_url` using the clause's `locator`. A clause whose quote cannot be extracted loads as NEEDS_COUNSEL.
7. The hub graph never stores which tenant uses which model. Tenant confirmations reach the hub only as salted hashes through the Publisher.
8. Demo companies and people are fictional and labelled "(fictional)". Never re-upload model weights anywhere.

## Engineering rules
- FalkorDB is the heart of the product (sponsor constraint): every answer and every memory write goes through FalkorDB; caches may hold raw Hugging Face HTTP responses only, never graph answers.
- Python 3.12, FastAPI, pydantic v2, httpx (async), `falkordb` client, `mcp>=1.10,<2` (mcp 2.x renamed FastMCP; do not upgrade). Next.js App Router with TypeScript for the web app.
- All Cypher lives in `services/api/app/graph/queries.py`, copied from `docs/queries.cypher`, parameterised. No string-built Cypher with user input.
- Bounded variable-length paths only (`*0..6`, `*1..6`). No unbounded `*`.
- Use `ro_query` for reads. Use MERGE on ids for idempotent writes.
- Every Hugging Face call goes through `app/hf/client.py`: shared rate limiter, `HF_TOKEN`, cache, 10 s timeout, 3 retries with backoff on 429/5xx, and a clear error when the Hub is unavailable.
- Every endpoint validates input (model ids match `^[\w.-]+/[\w.-]+$`), returns typed errors, and logs with a request id. No secrets in logs.
- Tests: pytest against a FalkorDB service container; golden verdict tests in `services/api/tests/golden/` must stay green. Add a test for every bug fixed.
- Do not commit secrets. `.env` is git-ignored; `.env.example` lists every variable.
- Git: conventional commits (`feat(api): ...`, `fix(web): ...`), one logical change per commit. Humans decide when to commit and push.

## Definition of done for any task
- Build passes, tests pass, the deployed `/api/health` is green.
- The README section affected is updated (data model, queries, setup, tracks, AI disclosure).
- The acceptance criteria in `docs/TASKS.md` are met and ticked.
