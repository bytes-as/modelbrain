# 3-minute demo video (G119, G154)

Record at 1440x900, browser zoom 110%. Before recording, run `docs/RUNBOOK.md` "Before recording" (reset the compounding demo, warm the pages). Use a fresh private window so no old sandbox is in sessionStorage. Every shot below works on the local stack today.

| Time | Shot | What to click and say | Track |
|---|---|---|---|
| 0:00-0:12 | Cold open on `/m/OPEA/Llama-3.2V-11B-cot-int4-sym-inc?hq=DE` | "This model card says apache-2.0. Its weights come from Llama 3.2 Vision. For a company in Berlin, that licence does not grant the rights at all." Show the red **BLOCKED** badge. | hook |
| 0:12-0:40 | Same page | Point at the path chips `OPEA → Xkev → meta-llama`, the quoted clause and its source link. Click **Flip HQ to US**: ALLOWED WITH OBLIGATIONS. Open **How we decided**: "Every answer is this Cypher query on FalkorDB, 17 ms." | Track 1 |
| 0:40-1:05 | Claude Code in a terminal | `claude mcp add --transport http modelbrain http://localhost:8000/mcp`, then ask "add OPEA/Llama-3.2V-11B-cot-int4-sym-inc to our pipeline for our German product". It calls `can_i_use` and answers BLOCKED with the path. (Optional second ask: "trace the weights of TroyDoesAI/Llama-3.1-8B-Instruct" → `trace_weights`.) | Track 1 |
| 1:05-1:45 | `/findings` | "Cards can be wrong. Weights can't. We read about 2 KB of each model's real weights with HTTP range requests and search them in FalkorDB's vector index." Point at `TroyDoesAI/Llama-3.1-8B-Instruct`: card says WTFPL, weights identical to Meta's Llama 3.1 8B Instruct. Scroll to **Declared parent and weights disagree**: `microsoft/UserLM-8b` declares Llama 3.1, weights match Llama 3 (0.9986 vs 0.9868). Click the TroyDoesAI row: the verdict page shows the chip "Weights match meta-llama/Llama-3.1-8B-Instruct · similarity 1.000". | Track 1 |
| 1:45-2:15 | `/hidden-lineage` | "A strict company refuses inferred lineage." Show tier 1, 1 confirmation, strict verdict CANNOT DETERMINE. Click **Confirm this edge as my sandbox company**: tier 1 → 3, two independent confirmations, strict verdict ALLOWED WITH OBLIGATIONS, decisions reopened. "Each company's confirmation stays in its own graph. The shared graph only sees a salted hash." | Track 2 |
| 2:15-2:45 | `/replay/xkev` | "On 9 July 2025 someone asked Xkev about its licence. 130 days later the author uploaded Meta's licence file. None of its 9 children got the fix." Click **Replay the fix in my sandbox**: 9 descendants walked, the Kestrel claims-vision decision reopened, review task for Lena Vogt (fictional). Click through to `/companies` to show the task. | Track 2 + 3 |
| 2:45-2:55 | `/eval` or the README eval line | "160 frozen cases. Zero false ALLOW. A card-only check matches 35%." | proof |
| 2:55-3:00 | Close on `/` | Repo URL, MCP command, "Automated screening, not legal advice." | close |

## Lines to avoid

Never say "stolen", "leaked", "violating" or "illegal", and never attribute intent to a named author. Say "the metadata and the weights disagree" and "the parent's obligations may apply".

## If something breaks while recording

- A verdict page spins: the model is being ingested. Wait, or use a model from the list above (all prewarmed).
- The compounding panel already shows tier 3: reset it (`POST /api/admin/demo/compounding`) and reload.
- The replay button says it could not run: clear the site's session storage (old sandbox) and click again.
