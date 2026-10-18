import Link from "next/link";

import { Disclaimer, Exhibit, ExhibitHeader, Part } from "../components/exhibit";

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

const GRAPHS: [string, string][] = [
  [
    "hub",
    "Public facts. Models, DERIVED_FROM edges with trust tiers, licences, clauses, file fingerprints and weight DNA vectors. Never stores which company uses which model.",
  ],
  [
    "tenant_*",
    "One per company. People, products, deployments, append-only rulings and the facts they rest on, events, tasks and playbooks. Kestrel and Harbor are fictional.",
  ],
  [
    "sbx_*",
    "One per visitor. A GRAPH.COPY of a fictional company. Everything you click writes here, expires after two hours, and never reaches the demo companies.",
  ],
];

const LINK = "text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent";

export default function HowItWorksPage() {
  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit H · Governing engine"
        source="FalkorDB"
        title={<>Obligations travel with the weights. The graph decides.</>}
        lede={
          <>
            Licence obligations travel with the weights, through every fine-tune, merge and
            re-upload. ModelBrain keeps that real lineage in FalkorDB and lets the graph decide. A
            language model may phrase an explanation; it never decides.
          </>
        }
        facts={[
          { value: GRAPHS.length, label: "Kinds of graph, one instance" },
          { value: 6, label: "Hops of ancestry, max" },
          { value: TIERS.length, label: "Trust tiers per edge" },
          { value: AGENTS.length, label: "Agents" },
        ]}
      />

      <Part
        n="1"
        title="One FalkorDB instance, three kinds of graph."
        note={
          <>
            A company&apos;s confirmation reaches the hub only as a salted hash. Two different
            hashes raise an edge to tier 3 for everyone; nobody learns who confirmed.
          </>
        }
      >
        <div className="ledger-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Graph</th>
                <th>Holds</th>
              </tr>
            </thead>
            <tbody>
              {GRAPHS.map(([graph, text]) => (
                <tr key={graph}>
                  <td className="whitespace-nowrap font-mono text-[13px]">{graph}</td>
                  <td className="min-w-[14rem] text-muted">{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Part>

      <Part
        n="2"
        title="What only the graph engine gives us."
        note="Stop FalkorDB and nothing answers: verdicts return 503, never a cached answer."
      >
        <ol className="grid gap-x-10 gap-y-8 md:grid-cols-2">
          {FALKOR.map(([title, body], index) => (
            <li key={title} className="grid grid-cols-[32px_minmax(0,1fr)] gap-2">
              <span className="font-mono text-sm text-muted">
                ({String.fromCharCode(97 + index)})
              </span>
              <div>
                <p className="font-serif text-2xl leading-snug">{title}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </Part>

      <Part
        n="3"
        title="Trust tiers on every edge."
        note="Default verdicts use tier 1 and above. Strict mode uses tier 2 and above and answers CANNOT DETERMINE when a parent is only inferred."
      >
        <div className="ledger-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Tier</th>
                <th>Evidence for the edge</th>
              </tr>
            </thead>
            <tbody>
              {TIERS.map(([tier, text]) => (
                <tr key={tier}>
                  <td className="w-16 font-mono text-[13px]">{tier}</td>
                  <td className="min-w-[14rem]">{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Part>

      <Part
        n="4"
        title="Agents and handoffs."
        note="Agents hand work to people through Task nodes. Approving a reopened review writes a new ruling that supersedes the old one."
      >
        <div className="ledger-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Duty</th>
              </tr>
            </thead>
            <tbody>
              {AGENTS.map(([name, text]) => (
                <tr key={name}>
                  <td className="whitespace-nowrap font-mono text-[13px]">{name}</td>
                  <td className="min-w-[14rem] text-muted">{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Part>

      <Part n="5" title="Read the queries.">
        <p className="max-w-3xl font-serif text-xl leading-relaxed">
          Every query is in{" "}
          <a
            className={`font-mono text-base ${LINK}`}
            href="https://github.com/bytes-as/modelbrain/blob/main/docs/queries.cypher"
          >
            docs/queries.cypher
          </a>
          . Try it:{" "}
          <Link className={LINK} href="/findings">
            weight DNA findings
          </Link>
          ,{" "}
          <Link className={LINK} href="/replay/xkev">
            the Xkev replay
          </Link>
          ,{" "}
          <Link className={LINK} href="/hidden-lineage">
            compounding
          </Link>
          .
        </p>
      </Part>

      <Disclaimer />
    </Exhibit>
  );
}
