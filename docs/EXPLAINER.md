# ModelBrain in two minutes (every team member must be able to say this)

**The problem.** A model on Hugging Face can say "apache-2.0" on its card while its weights come from Llama or Gemma. Obligations attach to the weights, not the card. About 22% of popular re-uploads don't even name a parent. When an upstream author fixes a licence, nobody downstream hears about it.

**What we built.** An agent system on FalkorDB that answers "can this team ship this model, for users here, and who must sign off?", shows the path and the quoted clause, remembers every decision per company, and reopens decisions when anything upstream changes.

**The graph model.**
- `hub` graph (public facts): `Model -[:DERIVED_FROM {relation, source, tier, conf}]-> Model`, `Model -[:DECLARES]-> License -[:IMPOSES]-> Clause`, `Model -[:HAS_FP]-> Fingerprint`, `Snapshot`, `Discussion`.
- One graph per company, plus per-visitor sandboxes: `Person`, `Team`, `Product`, `Deployment`, `Ruling -[:RESTS_ON]-> Fact`, `Event`, `Task`, `Conversation`, `Playbook`.
- Edge tiers are trust levels: 0-1 inferred, 2 declared, 3 confirmed by two organisations, 4 confirmed by the author.

**The queries you must be able to explain.**
- **Q1** walks every ancestry path (bounded to 6 hops, through merges) at a minimum trust tier and collects each licence's clauses. This is the verdict.
- **Q2** finds the top of each path; if it is not a known base model, the lineage is incomplete and the honest answer is CANNOT DETERMINE.
- **R1** runs FalkorDB's connected-components algorithm over shared file hashes to unmask re-uploads that hide their parent.
- **D1** walks downstream from a changed model to every descendant; **T3** finds every company ruling that rested on any of them; they reopen as tasks for the owner.
- **P1** records a salted hash of each confirming company on an edge; two independent confirmations raise its tier for everyone, without revealing who.
- **W2** searches FalkorDB's vector index over 1,024 sampled weight values per model: it finds the true parent of a model whose card names none (or names the wrong one). **W7/W8** recover two-parent merges and how much of the weights trace to each root.
- **A1-A4**: PageRank ranks models that spread a wrong licence label; betweenness finds chokepoints; label propagation finds families; shortest path gives a proof path or proves there is none.

**Why FalkorDB, and why it is load-bearing.** Every verdict, path, fan-out and memory read is a FalkorDB query; stop FalkorDB and the product returns 503 instead of answers. One instance holds the shared hub, every company's private graph and every visitor's sandbox (`GRAPH.COPY`). Traversals are fast enough to run inside every agent call over MCP.

**Decisions and trade-offs.**
- The model suggests, the graph decides: verdicts are deterministic; the LLM only phrases explanations.
- Licence text is never stored in our repo: quotes are extracted at runtime from the official sources.
- We never post to anyone else's repo; the live loop runs on our own test repo.
- Strict mode refuses to guess: inferred lineage alone gives CANNOT DETERMINE.

**The moat.** Anyone can read model cards. We read the weights: about 2 KB per model through HTTP range requests, compared in FalkorDB. That index of who-really-came-from-whom is something only we compute, and it grows with every crawl.

**What we would do next.** More licences, real customer tenants, webhooks from the Hub instead of polling, and an AI bill-of-materials export.
