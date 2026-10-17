# Prompt to paste into Cursor (Agent mode)

You are building ModelBrain v3 for the Graph Hacks hackathon (WeMakeDevs x FalkorDB). Submissions close Sunday 18 Oct 2026, 11:59 PM IST.

Before writing any code, read these files in this order and treat them as binding:
1. `AGENTS.md` (rules)
2. `BLUEPRINT.md` section 0 (document map and precedence), then the rest of BLUEPRINT.md
3. `docs/GOALS.md` (138 numbered goals with acceptance tests: your work list)
4. `docs/FLOWS.md`, `docs/API.md`, `docs/UI.md`, `docs/queries.cypher`, `docs/REQUIREMENTS.md`
5. `data/*` and `docs/OPEN_POINTS.md`

How to work:
- Work through `docs/GOALS.md` from G001 in order. For each goal: implement it, run its Verify step, and only then tick it with the date. Do not start the next milestone while any goal in the current one fails its Accept condition.
- FalkorDB is the heart of the product. Every answer and every memory write goes through FalkorDB using the Cypher in `docs/queries.cypher` (copy it verbatim into `services/api/app/graph/queries.py`). Never compute ancestry or verdicts in Python and only store them in the graph.
- Pin `mcp>=1.10,<2`. Mount MCP exactly as BLUEPRINT section 3 describes.
- Never paste licence text into the repo. The Clause Loader extracts quotes at runtime using the locators in `data/clauses.seed.json`.
- Do not write `eval/labels.json` yourself. A human writes it (G050). Stop and ask when you reach that point.
- If two documents disagree, follow the precedence order in BLUEPRINT section 0 and write the conflict under "Questions for the owner" in `docs/TASKS.md`.
- If something in the docs is impossible or wrong, do not improvise silently: write it under "Questions for the owner" and continue with the next goal you can do.
- Protect the hour-8 core (G030-G049). Never break it while building later goals.
- If time runs short, cut only goals marked *(cuttable)*, in the order of BLUEPRINT section 14 and section 18, and strike them through with a reason.
- Commit after each completed goal with a conventional commit message (`feat(api): ...`, `fix(web): ...`). Do not push until the owner says so.

At the end of every milestone (M1 to M8), stop and post a short report: goals done, goals failing with the exact error output, anything cut, and questions for the owner.

Start now with G001.
