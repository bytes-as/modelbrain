# Open points

## Resolved before handoff (18 Oct 2026)
| Point | Resolution | Evidence |
|---|---|---|
| Licence quotes had to be typed in by hand | Quotes are no longer stored in the repo. The Clause Loader extracts each one at runtime from the official licence text using a short locator. 33 of 34 locators were verified against the live sources; OpenRAIL stays NEEDS_COUNSEL by design | `data/clauses.seed.json` (`locator`, `source_raw_url`, `locator_verified`), FLOWS F3 |
| Does Llama 4 carry the EU exclusion for multimodal models? | Yes, the clause is present in the Llama 4 Acceptable Use Policy | `data/clauses.seed.json` licence `llama4` note |
| MCP server mounting inside FastAPI | Works with `mcp` 1.30.0: `FastMCP("modelbrain", stateless_http=True)`, `app.mount("/", mcp.streamable_http_app())` after routes, lifespan runs `mcp.session_manager.run()`; `initialize`, `tools/list`, `tools/call` all succeed at `/mcp`. **mcp 2.x renamed FastMCP to MCPServer: pin `mcp>=1.10,<2`** | BLUEPRINT section 3 |
| Hugging Face commit and discussion fields | Commits: `{id, title, message, date, authors}`. Discussions: `{num, title, status, createdAt, author, isPullRequest, numComments, ...}` inside `{discussions, count, numClosedDiscussions, start}` | BLUEPRINT section 4, FLOWS F11 |
| FalkorDB container data path and persistence | Data at `/var/lib/falkordb/data`; Redis options via `REDIS_ARGS` (`--appendonly yes --requirepass ...`); module options via `FALKORDB_ARGS`. **The default query timeout is 1000 ms; set `TIMEOUT 5000`.** The image runs without a password, so set `requirepass` and keep it on private networking | BLUEPRINT section 3, FLOWS F14, `docker-compose.yml` |
| `GRAPH.COPY`, zero-length paths, algorithm signatures | All verified on `falkordb/falkordb:latest`: `*0..6`, `algo.WCC`, `algo.pageRank`, `algo.betweenness`, `algo.labelPropagation`, `shortestPath` (NULL when no path), `algo.SSpaths`, `GRAPH.COPY` (destination must not exist) | `docs/queries.cypher` header |
| Two query bugs | Q1 returned placeholder clauses when a licence had none (now `CASE WHEN c IS NULL`); Q3 returned duplicate edges (now `RETURN DISTINCT`) | `docs/queries.cypher` |
| Hosting | Vercel for the web app; Railway for the API and FalkorDB in Docker. FalkorDB Cloud free tier rejected (stops after 1 day idle, deleted after 7 days) | BLUEPRINT section 3 |

## Deferred to the end (safe to leave until the build is done)
| Point | Why it can wait | When | Owner |
|---|---|---|---|
| Hugging Face discussion **posting** payload (`POST /api/models/{repo}/discussions`) | Only needed for the live loop (G089), which is cuttable; the Xkev replay covers the story | Block 5, before G089 | A |
| Exact Hub search used to find 2 more parentless re-uploads for the eval set | The 3 verified ones are enough for the demo | Block 4, during G050 | B |
| `data/alternatives.json` ids exist on the Hub | Alternatives only show on BLOCKED verdicts; a missing id is skipped | Block 6 | A |
| Repository licence and ownership (rule 15) | Needed only at submission | Block 7, G115 | Team |
| Blog post (side prize) | After submission is fine | After G121 | B |

## Not open (decided; do not revisit)
See BLUEPRINT section 16.5.
