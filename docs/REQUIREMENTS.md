# Requirements traceability

Every requirement and judging signal on the hackathon page (overview, tracks, sponsor section, FAQ), the rules page and the schedule, mapped to where ModelBrain meets it and the goal in `docs/GOALS.md` that proves it. Source pages: https://www.wemakedevs.org/hackathons/falkordb, `/rules`, `/schedule`, `/resources` (read 17-18 Oct 2026).

**Prime constraint: FalkorDB is the heart of the product.** The sponsor is FalkorDB; the FAQ says it must be the primary graph database and support a central part of the product, and rule 3 disqualifies a graph that is only decoration. Section C lists every FalkorDB capability we use. Row ids: H = hard rule, S = judging signal (not to be confused with query names in `docs/queries.cypher`).

## H. Hard rules (failing any of these risks disqualification)

| # | Requirement (source) | How ModelBrain meets it | Goals |
|---|---|---|---|
| H1 | FalkorDB must be the primary graph database and support a central part of the product (FAQ; rule 2) | Every verdict, lineage view, fan-out, ruling and task lives in FalkorDB; no other database | G010-G016, G030-G045 |
| H2 | The graph must do real work: if the product works without FalkorDB, it is decoration (rule 3) | Verdicts are Cypher traversals (Q1, Q2) plus graph algorithms (WCC, PageRank, betweenness, shortest path); a test proves the verdict endpoint fails without FalkorDB | G044, G103 |
| H3 | Main coding and the FalkorDB implementation are new work during the event (FAQ; rule 8) | All code written 18 Oct; only libraries and templates reused | G001 |
| H4 | Data must be public, synthetic or own; no private, login-protected, paywalled or personal data (rule 6) | Public Hugging Face Hub metadata and public licence texts; fictional companies and people; no personal data stored; gated model files are not fetched without an accepted token, and only metadata and hashes are used | G020-G029, G060 |
| H5 | Public source-code repository (rule 10) | GitHub public repo | G115 |
| H6 | README with setup instructions and the graph data model (rule 10) | README sections "Run locally", "Deploy", "Graph data model" | G116, G117 |
| H7 | The Cypher queries or graph algorithms the product depends on (rule 10) | README section "Queries and algorithms" linking `docs/queries.cypher`, explaining Q1, Q2, R1, D1, P1, T3, A1-A4 | G118 |
| H8 | Demo video showing the working project (rule 10; FAQ) | 3-minute video per BLUEPRINT section 15 | G119 |
| H9 | Live deployment, or complete local setup if it cannot be deployed (rule 10; FAQ "live deployment preferred") | Vercel web + Railway API + Railway FalkorDB; `docker compose up` local path also documented | G100-G102, G116 |
| H10 | Name every track entered at submission (rule 5) | Submit to Track 1 (primary), Track 2, Track 3 | G121 |
| H11 | AI coding assistants allowed but must be disclosed (rule 11; FAQ) | README section "Built with AI assistance" naming Claude and Cursor and what they did | G120 |
| H12 | Participants understand and can explain the graph model, queries, architecture and decisions (rule 12; FAQ "responsible for code, architecture, security, correctness") | `docs/EXPLAINER.md` one-page talk track; every team member rehearses it | G122 |
| H13 | Not entirely AI-generated without meaningful contribution, verification or understanding (rule 13) | Humans write the eval labels, review every PR, verify licence locators, and run the demo | G050, G122 |
| H14 | Solo or up to 4 per team; each person in one team (rule 1) | Team registered on WeMakeDevs | G121 |
| H15 | Respect, no plagiarism, no judging manipulation (rules 16-18) | We do not copy other entries; competitor names appear only in our private notes, never in the submission | G124 |
| H16 | Submissions close 18 Oct 2026, 11:59 PM IST (rule 7; schedule) | Build plan ends at H23 with a 1 h buffer | G121 |
| H17 | Run FalkorDB however suits you: Docker, self-hosted or FalkorDB Cloud; any language, framework, frontend or platform (rule 4) | FalkorDB in Docker (`falkordb/falkordb:latest`) on Railway and locally; FalkorDB Cloud is an allowed managed fallback | G002, G100 |
| H18 | Frameworks, open-source libraries, public APIs, templates and public datasets may be used; the original work done during the event is what is judged (rule 9) | Our original work: the graph model, clause engine, resolver, fan-out, agents, MCP tools, UI; dependencies listed in README | G117 |
| H19 | IP belongs to the team; agree on ownership before submitting (rule 15) | Team agrees ownership and adds a LICENSE file (MIT suggested) before submission | G125 |
| H20 | WeMakeDevs Code of Conduct applies (rules 16-18) | Respectful conduct; no plagiarism; no judging manipulation | G124 |

## S. What the brief and tracks ask for (judging signals)

| # | Signal (source) | Where ModelBrain shows it | Goals |
|---|---|---|---|
| S1 | "Build a working agent, or a group of agents, with FalkorDB as its context layer. The graph has to shape what the agent does" (challenge) | Scout, Resolver, Auditor, Watcher, Notifier and Publisher agents read and write FalkorDB on every step; the MCP tool lets external agents act on graph answers | G030-G090 |
| S2 | "An agent that acts on connected data, remembers what it learns, and can show how it got to each answer" (brief) | Acts: verdicts, blocked PRs, drafted fixes. Remembers: rulings per company, confirmed edges in the hub. Shows: path + quoted clause + Cypher on every verdict | G040-G049, G070-G079 |
| S3 | Work the graph has to do: "Follow connections across data" | Model ancestry across finetune, adapter, merge, quantised and mirror edges (Q1, A4, A5) | G031 |
| S4 | "Remember across sessions" | Rulings, facts and events persist per tenant; confirmations persist in the hub; reopen on change | G060-G069 |
| S5 | "Share state between agents" | Task nodes with leases and HANDED_OFF_FROM; Watcher -> Auditor -> owner handoff | G066-G068, G082 |
| S6 | "Connect people, projects, and decisions" | Tenant graph: Person, Team, Product, Deployment, Ruling, Event, SIGNED | G061, G064 |
| S7 | "Show the path behind an answer" | Path graph, quoted clause, edge tiers and Cypher on every verdict; `explain` MCP tool | G045-G047 |
| S8 | "Pick a task where the answer depends on how things connect" | A model's obligations depend on every ancestor through merges and hidden re-uploads | G031, G055 |
| S9 | Track 1 key focus: multi-hop reasoning | Q1 bounded multi-hop ancestry through multi-parent merges | G031, G033 |
| S10 | Track 1: graph queries and algorithms as agent tools | MCP tools `lineage`, `explain`, plus `relabel_hubs` (A1 PageRank), `chokepoints` (A2 betweenness), `families` (A3 community detection), `proof_path` (A4 shortest path) | G074-G077 |
| S11 | Track 1: tool selection through MCP | `/mcp` server; Claude Code chooses `can_i_use` vs `explain` vs `lineage` by tool descriptions | G070-G073 |
| S12 | Track 1: actions based on what the graph shows | Block a PR (GitHub Action), open a review task, draft a card fix | G083-G089 |
| S13 | Track 1: explainable results | Every verdict carries path, clause quote with source link, tiers and the Cypher | G045-G047 |
| S14 | Track 2: episodic, semantic and procedural memory | Episodic: rulings and events per tenant. Semantic: hub facts (licences, clauses, lineage, tiers). Procedural: the clause rules and task playbooks stored as graph nodes (`(:Playbook)` per task kind) | G062, G069 |
| S15 | Track 2: persistent conversation history | MCP sessions and web "ask" history stored as `(:Conversation)-[:HAS_TURN]->(:Turn)` per tenant, linked to the rulings they produced | G078 |
| S16 | Track 2: shared state and handoffs between agents | Tasks, leases, HANDED_OFF_FROM, Watcher -> Auditor -> owner | G066-G068 |
| S17 | Track 2: high-concurrency reads and writes | Read-only `ro_query` for verdicts; idempotent MERGE writes; 409 on stale ruling writes; a load test of 50 concurrent verdicts | G067, G104 |
| S18 | Track 2: separate memory per user or tenant | One FalkorDB graph per company and per visitor sandbox (`GRAPH.COPY`), on one instance | G063, G065 |
| S19 | Track 3: knowledge from docs, tickets and chats in one graph | Model cards, licence documents and Hub discussions (the AI supply chain's docs and tickets) in the hub; internal decisions in the tenant graph | G024, G087 |
| S20 | Track 3: who owns what, and who knows what | Person OWNS Deployment; Team OWNS Product; who signed each ruling | G061, G064 |
| S21 | Track 3: tracing decisions back to their source | T7 decision trace: ruling -> facts -> commit sha -> clause quote -> source URL | G064 |
| S22 | Track 3: keeping knowledge current as things change | Watcher + reopen-on-change + supersede | G080-G082 |
| S23 | Track 3: answers with clear sources | Every answer cites licence URL + section + commit sha | G045 |
| S24 | "What breaks if this service goes down?" style questions (why graphs) | "What reopens if this upstream model changes?" (D1 fan-out) | G080 |
| S25 | Prize "best agent that uses a graph to make decisions and take action" (T1) | Primary track narrative | G119 |
| S26 | Side prize: best blog post | Blog post drafted from README | G123 |
| S27 | Top 50 projects get T-shirts | Polish, live URL, clear README | G100-G120 |

## C. FalkorDB capabilities we use (the sponsor section, line by line)

| Sponsor claim | Our use | Goals |
|---|---|---|
| "Traversals are fast enough to run on every step of an agent loop" | Every MCP call and CI check runs Q1/Q2 live; p95 under 300 ms for cached models is a goal | G104 |
| "One instance can hold thousands of isolated graphs, so each user, agent, or tenant gets its own" | `hub` + `tenant_*` + `sbx_*` on one instance; `GRAPH.COPY` creates visitor sandboxes | G063, G065 |
| "Run it locally with Docker" | `docker compose up` with `falkordb/falkordb:latest` | G002 |
| Official clients | `falkordb` Python client | G010 |
| Cypher: match patterns, follow paths, return what the agent needs | All queries in `docs/queries.cypher` | G010-G016 |
| Context for AI agents: agent memory, multi-agent state, connected company knowledge | Tenant rulings and conversations; tasks and handoffs; company deployment graph | G060-G069 |
| Connect your agent stack: MCP | Our MCP server; optional: document read-only use of the official FalkorDB MCP server against the hub | G070-G073, G079 |
| Connect your agent stack: GraphRAG-SDK, QueryWeaver, Graphiti, Cognee, LangChain, LlamaIndex | "Ask the company brain": an LLM (via OpenRouter) selects one of 8 templated Cypher questions (tool selection), FalkorDB answers with sources; QueryWeaver text-to-Cypher optional behind a flag | G079, G135 |
| One graph per user or tenant (multigraph topology) | Tenant and sandbox graphs | G063, G065 |
| Graph algorithms as agent tools: shortest path, PageRank, centrality, connected components, community detection | A4 shortestPath (proof path), A1 PageRank (relabel hubs), A2 betweenness (chokepoints), R1 WCC (hidden lineage), A3 labelPropagation (families) | G052-G055, G074-G077 |
| Explore the graph with FalkorDB Browser | Local compose exposes the Browser on port 3000; README shows judges how to inspect the hub and a tenant graph; screenshots in README | G118 |

## F. Add-ons and the signals they strengthen
| Add-on | Signal | Goals |
|---|---|---|
| Hosted path (OpenRouter catalogue: providers, datacenters, hosted models) | S3 follow connections across data; S12 actions based on the graph; real public data; new no-path proof (no EU-resident provider) | G128-G131 |
| Licence text watch | S22 keeping knowledge current; S4 remember across sessions | G132 |
| Ask the company brain with LLM tool selection | S11 tool selection; S23 answers with clear sources; Track 3 "answer questions and get work done" | G135, G136 |
| Multi-LLM card-only baseline | H2 the graph is not decoration (measured) | G127 |
| Custom licence resolution, web fetcher | fewer CANNOT DETERMINE answers without guessing | G133, G134 |
| Voice | demo presentation only | G137 |

## E. Official resources (from the Resources page) and where we use them
| Resource | Use |
|---|---|
| Getting started: https://docs.falkordb.com/getting-started/ | Block 0 setup |
| Docs: https://docs.falkordb.com/ ; Cypher: https://docs.falkordb.com/cypher/ | All queries |
| Docker and Compose: https://docs.falkordb.com/operations/docker | `docker-compose.yml`, Railway service (data path `/var/lib/falkordb/data`, `REDIS_ARGS`, `FALKORDB_ARGS`) |
| FalkorDB Cloud: https://app.falkordb.cloud/ | Allowed fallback; free tier unsuitable for judging (stops after 1 day idle, deleted after 7 days) |
| FalkorDB Browser: https://docs.falkordb.com/browser/ | README walkthrough and screenshots for judges (port 3000 locally) |
| Clients: https://docs.falkordb.com/getting-started/clients | `falkordb` Python client |
| Algorithms: https://docs.falkordb.com/algorithms/ | WCC, PageRank, betweenness, label propagation, shortest path, SSpaths |
| Integrations: https://docs.falkordb.com/integration/ | MCP; QueryWeaver stretch (G079) |
| GraphRAG SDK: https://github.com/FalkorDB/GraphRAG-SDK | Not used in the core (our ontology is explicit); mentioned in README as considered |
| Community projects: https://www.falkordb.com/community-projects/ | Check before submission that we are not duplicating a listed project |
| Blog, How to build an agent that reasons over a graph: https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph | Read in Block 0; align README vocabulary with it |
| FalkorDB Discord: https://discord.com/invite/Y2mMT9VdMy | Ask if blocked on a FalkorDB feature |

## D. Gaps we accept (stated honestly in the README)
- Company graphs are fictional; the hub data is real.
- Licence verdicts are automated screening, not legal advice; NEEDS_COUNSEL is returned whenever a clause cannot be resolved.
- Compounding starts with two demo tenants plus our crawl; the mechanism, not the network size, is what we demonstrate.
