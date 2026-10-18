import Link from "next/link";

const FALKOR: [string, string][] = [
  [
    "Many graphs in one instance, GRAPH.COPY",
    "A shared hub, one private graph per company, and a sandbox per visitor cloned in one command. A company's rulings never touch the hub.",
  ],
  [
    "Vector index inside the graph",
    "1,024 sampled weight values per model, searched with db.idx.vector.queryNodes and filtered by graph properties in the same query.",
  ],
  [
    "Vector search + traversal + clauses in one query",
    "From a model's weights to its nearest parent, up the trusted ancestry, to the licence clauses: one Cypher statement, a few milliseconds.",
  ],
  [
    "Bounded variable-length traversal",
    "Every ancestry path up to 6 hops, through merges, at a minimum trust tier; every descendant for the reverse fan-out.",
  ],
  [
    "Algorithms in Cypher",
    "WCC unmasks re-uploads by shared fingerprints; PageRank ranks relabel hubs; betweenness finds chokepoints; label propagation finds families; shortest path proves a derivation or its absence.",
  ],
  [
    "Properties on edges, read inside paths",
    "Trust tiers, salted confirmer hashes, weight similarity and merge shares live on the edge; strict mode and merge exposure are enforced in the traversal itself.",
  ],
];

const TIERS: [string, string][] = [
  ["0", "Weak inference: config fingerprint only"],
  ["1", "Strong inference: identical file hash, tokenizer + config, or weights that match"],
  ["2", "Declared on the model card"],
  ["3", "Confirmed by two independent companies (salted hashes)"],
  ["4", "Confirmed by the model's author"],
];

const AGENTS: [string, string][] = [
  ["Scout", "Ingests a model and its ancestors from the Hub, keyed by canonical id."],
  [
    "Resolver",
    "Infers hidden parents from file hashes (WCC) and from the weights (vector search).",
  ],
  ["Auditor", "Decides a verdict from the graph and writes an append-only ruling."],
  ["Watcher", "Re-reads watched models, diffs them, and reopens rulings down the lineage."],
  ["Publisher", "Turns a company's confirmation into a salted hash on the shared edge."],
];

function Layer({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded border border-white/10 bg-surface p-4">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted">{body}</p>
    </div>
  );
}

export default function HowItWorksPage() {
  return (
    <main className="[overflow-wrap:anywhere]">
      <h1 className="text-3xl">How it works</h1>
      <p className="mt-2 max-w-3xl text-muted">
        Licence obligations travel with the weights, through every fine-tune, merge and re-upload.
        ModelBrain keeps that real lineage in FalkorDB and lets the graph decide. A language model
        may phrase an explanation; it never decides.
      </p>

      <section className="mt-8">
        <h2 className="text-xl">One FalkorDB instance, three kinds of graph</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <Layer
            title="hub (public facts)"
            body="Models, DERIVED_FROM edges with trust tiers, licences, clauses, file fingerprints and weight DNA vectors. Never stores which company uses which model."
          />
          <Layer
            title="tenant_* (one per company)"
            body="People, products, deployments, append-only rulings and the facts they rest on, events, tasks and playbooks. Kestrel and Harbor are fictional."
          />
          <Layer
            title="sbx_* (one per visitor)"
            body="A GRAPH.COPY of a fictional company. Everything you click writes here, expires after two hours, and never reaches the demo companies."
          />
        </div>
        <p className="mt-3 text-sm text-muted">
          A company&apos;s confirmation reaches the hub only as a salted hash. Two different hashes
          raise an edge to tier 3 for everyone; nobody learns who confirmed.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-xl">What only the graph engine gives us</h2>
        <ul className="mt-3 space-y-3">
          {FALKOR.map(([title, body]) => (
            <li key={title} className="rounded border border-white/10 p-3">
              <p className="font-medium">{title}</p>
              <p className="mt-1 text-sm text-muted">{body}</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">
          Stop FalkorDB and nothing answers: verdicts return 503, never a cached answer.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-xl">Trust tiers on every edge</h2>
        <table className="mt-3 text-left text-sm">
          <tbody>
            {TIERS.map(([tier, text]) => (
              <tr key={tier} className="border-t border-white/10">
                <td className="py-2 pr-4 font-mono">{tier}</td>
                <td className="py-2">{text}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-sm text-muted">
          Default verdicts use tier 1 and above. Strict mode uses tier 2 and above and answers
          CANNOT DETERMINE when a parent is only inferred.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-xl">Agents and handoffs</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {AGENTS.map(([name, text]) => (
            <li key={name}>
              <span className="font-medium">{name}:</span> {text}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-sm text-muted">
          Agents hand work to people through Task nodes. Approving a reopened review writes a new
          ruling that supersedes the old one.
        </p>
      </section>

      <p className="mt-8 text-sm">
        Every query is in{" "}
        <a
          className="text-accent"
          href="https://github.com/bytes-as/modelbrain/blob/main/docs/queries.cypher"
        >
          docs/queries.cypher
        </a>
        . Try it:{" "}
        <Link className="text-accent" href="/findings">
          weight DNA findings
        </Link>
        ,{" "}
        <Link className="text-accent" href="/replay/xkev">
          the Xkev replay
        </Link>
        ,{" "}
        <Link className="text-accent" href="/hidden-lineage">
          compounding
        </Link>
        .
      </p>
      <p className="mt-6 text-sm text-muted">Automated screening, not legal advice.</p>
    </main>
  );
}
