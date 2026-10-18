# ModelBrain web app specification

Next.js (App Router, TypeScript, Tailwind) deployed on Vercel. Calls the API at `NEXT_PUBLIC_API_URL`. Every page works at 375 px wide. Every verdict view shows the disclaimer "Automated screening, not legal advice."

## Visual language
- Background near-black slate (`#0f1419`), surface `#161d25`, text `#e6ebf0`, muted `#98a3b1`, one accent teal `#43c2cb`. Light mode optional.
- Verdict colours (semantic, not accent): ALLOWED green `#2fbf71`, ALLOWED WITH OBLIGATIONS amber `#e9b450`, BLOCKED red `#f0605a`, CANNOT DETERMINE grey `#9aa3ae`, QUEUED blue `#5aa9f0`.
- Edge styles in graphs: declared = solid; inferred tier 1 = dashed; inferred tier 0 = dotted; tier 3 confirmed = gold solid; tier 4 author-confirmed = gold thick. Root models drawn larger with a crown icon.
- Typeface: Inter Tight for headings, Inter for body, JetBrains Mono for ids and Cypher.

## Global layout
- Top bar: logo "ModelBrain", nav: Check a model, Findings, Companies, Xkev replay, Live loop, MCP, Eval, How it works. A thin status dot reads `/api/health` (green up, amber degraded, red down with a banner "The graph database is restarting. Try again in a minute.").
- Footer: "Built for Graph Hacks with FalkorDB · Automated screening, not legal advice · Data: Hugging Face Hub public metadata and official licence texts · Companies shown are fictional."

## Pages

### `/` Check a model
- Heading: "Can you ship this model?" Sub: "Paste any Hugging Face model id. We follow its real ancestry in FalkorDB and tell you what its upstream licences require for your company."
- Input `model_id` (placeholder `owner/model`), example chips: `OPEA/Llama-3.2V-11B-cot-int4-sym-inc`, `SicariusSicariiStuff/Llama-3.2-1B_Base_FP8`, `grimjim/llama-3-Nephilim-v1-8B`, `Qwen/Qwen2.5-7B-Instruct`, `princeton-nlp/gemma-2-9b-it-SimPO`.
- Context controls: HQ country select (default Germany), "Commercial product" toggle (on), "We redistribute the weights" toggle (off), markets multi-select (default HQ), monthly active users number (0), "Strict mode (only declared or confirmed lineage)" toggle (off).
- Button "Check". On submit navigate to `/m/<owner>/<name>?hq=DE&c=1&dw=0&mau=0&strict=0`.

### `/m/[owner]/[name]` Verdict
States:
- Loading (< 4 s): skeleton with "Following the model's ancestry in FalkorDB…".
- Queued (202): progress list streamed from SSE: "Ingested meta-llama/Llama-3.2-11B-Vision-Instruct", …; then auto re-request.
- Error: envelope message + hint + "Try again".
Content when done:
1. Verdict badge (big) + one-line reason, e.g. "BLOCKED for a company based in Germany".
2. Declared vs inherited strip: "Card declares apache-2.0 · Inherits Llama 3.2 Community License" (shown only when `declared_differs`).
3. Context chips with "change" links; a "Flip HQ to US" quick action for EU contexts.
4. Lineage graph (react-force-graph-2d): queried model on the left, roots on the right, edges styled by tier, nodes coloured by declared licence family; clicking a node opens its Hub page in a new tab. Edge chips on the path (addendum section 9): `weights` → **"Weights match {parent} · similarity {sim}"** (tooltip: *"We compared a small sample of the actual weight values. The model card does not declare this parent."*); declared edge with `weights_sim` → **"Declared · confirmed by weights {sim}"**; merge edge → **"Merge · {share:.0%} of sampled weights from {parent}"**; licence from GGUF → **"Licence read from the GGUF file header"**. When W8 returns rows, show under the path: "About {exposure:.0%} of the sampled weights trace to {root} ({licence})".
5. Clause cards: blocking first, then needs counsel, then obligations. Each: summary (our words), quote block (verbatim from source, labelled "From the licence"), section, "Source" link, the path that carried it, obligation status pill.
6. Alternatives (only BLOCKED): "Alternatives in our candidate set" with their verdict pills; or "No compliant alternative in our candidate set."
7. "How we decided" collapsible: the two Cypher queries (Q1, Q2) with parameters, execution time, edge tiers legend.
8. Actions: "Save as a ruling for a company" (opens tenant picker; creates a sandbox if needed), "Draft a note to the model author" (only when `declared_differs`; creates a draft and an approval task), "Copy MCP command".
9. Disclaimer line.

### `/companies`
- Two columns: Kestrel Analytics GmbH (fictional, Germany) and Harbor Apps Inc. (fictional, US); plus "Your sandbox" column if one exists.
- Per company: products -> deployments table (model id, owner, latest verdict pill, decided at, "trace" link), open tasks list with Claim/Approve/Reject buttons (sandbox only), events timeline (REOPENED, APPROVED, CONFIRMED_EDGE, SUPERSEDED).
- Button "Try it as this company" -> `POST /api/sandbox` -> token in sessionStorage -> column switches to the sandbox.
- Trace drawer (`/api/tenants/{t}/rulings/{id}/trace`): verdict, facts (model id, commit sha linking to the Hub commit, licence, clause ids), events with who signed.

### `/findings` — "Where metadata and weights disagree"
- Coverage line from W6: "Fingerprinted {ok} of {total} models; {gated} gated; {quantized} in formats we don't sample yet."
- Table 1 (W4): "Weights match a parent the card does not declare" — columns: model (Hub link), format, card licence, weights parent (Hub link), score or share, root, root licence.
- Table 2 (W5): "Declared parent and weights disagree" — model, declared parent, weights parent, similarity.
- Table 3: top merges with exposure (W8 sample rows).
- Copy follows addendum section 1.2: say "metadata and weights disagree", "weights closely match", "the card does not declare this parent", "obligations of the parent may apply"; never stolen, leaked, fake, violates, infringes. Disclaimer on the page.
- Playwright must fail if forbidden words from section 1.2 appear anywhere on this page.

### `/hidden-lineage`
- List of WCC components with unmasked re-uploads: "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8 names no parent; shares tokenizer and config with meta-llama/Llama-3.2-1B (inferred, confidence 0.8)".
- "Confirm as Kestrel" / "Confirm as Harbor" buttons (sandbox) showing the tier change and the flipped strict verdict.
- Relabel hubs table (A1 PageRank) and chokepoints table (A2 betweenness), families (A3) as small multiples.

### `/replay/xkev`
- Timeline scrubber with events from `/api/replay/xkev`: 2025-07-09 discussion opened; 2025-11-16 card update; 2025-11-16 licence file uploaded; "card still declares apache-2.0".
- Fan-out panel: the 9 children as tiles; at the fix event each turns "did not inherit the fix"; counter "Fix leverage: 9 of 9 descendants unchanged".

### `/live-loop`
- Our allowlisted test repo card, draft text, Approve button (admin only), posted discussion link, "Check now" button, before/after edge tier, reopened rulings list.
- For visitors (not admin): read-only replay of the last loop run with timestamps.

### `/mcp`
- Command block: `claude mcp add --transport http modelbrain https://<api-host>/mcp` with copy button; Cursor config JSON snippet; tool table from `docs/API.md`; a short screen recording of Claude Code calling `can_i_use`.

### `/eval`
- Labels hash (from `eval/labels.sha256`), metrics cards (accuracy, false ALLOW count, CANNOT DETERMINE rate, declared-differs precision/recall), comparison table vs declared-licence baseline and card-only LLM baseline, per-case table with filters.

### `/how-it-works`
- Diagram of the three graph layers (hub, tenants, sandboxes) on one FalkorDB instance; edge tiers; the privacy rule; the agents and their handoffs; the algorithms used and why; link to the repo and `docs/queries.cypher`.

## Copy rules
- Never "violating", "illegal", "infringing", "stolen", "leaked", "fake", "violates", "infringes". Use "may not be permitted", "metadata and weights disagree", "weights closely match", "the card does not declare this parent", "obligations of the parent may apply", "needs counsel". Prefer "machine-readable metadata" when prose on the card explains lineage the Hub fields omit.
- Name companies and people with "(fictional)".
- Error messages say what went wrong and how to fix it, no apologies.

## Add-on UI (BLUEPRINT section 18)
- Verdict page: a "How do you run it?" switch: "Our own copy of the weights" (default) or "Through an API provider". The second shows a hosted-model search (from `/api/hosted`), a "Data must stay in" select (EU, US, specific countries), and a providers panel listing each provider with headquarters, datacenters, quantisation, uptime and terms link; when none qualify, a grey card: "No provider in our catalogue serves this model from an allowed datacenter."
- ~~`/companies`: "Ask this company" box~~ (cut 18 Oct 2026; was G079/G135/G137).
- `/how-it-works`: add the Provider and LicenseText layers to the diagram.
- Copy: "Through an API provider" verdicts on Llama multimodal models show "Needs counsel: you call the model through a provider; whether the end-user exemption covers your product is a legal question."
