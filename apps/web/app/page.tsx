import Link from "next/link";

import { Schedule, SimilarityScale } from "./home/evidence";
import { RedlineHero } from "./home/redline-hero";

function Clause({
  n,
  title,
  children,
  tone = "paper",
}: {
  n: string;
  title: React.ReactNode;
  children: React.ReactNode;
  tone?: "paper" | "paper-2" | "graphite";
}) {
  const ground =
    tone === "graphite"
      ? "bg-bg text-text"
      : tone === "paper-2"
        ? "bg-paper-2 text-ink"
        : "bg-paper text-ink";
  const meta = tone === "graphite" ? "text-muted border-white/15" : "text-ink-soft border-ink/20";
  const heading = tone === "graphite" ? "text-text" : "text-ink";
  return (
    <section className={`bleed ${ground}`}>
      <div className="mx-auto max-w-6xl px-4 py-14 md:py-20">
        <div className={`grid gap-6 border-t pt-6 md:grid-cols-[120px_minmax(0,1fr)] ${meta}`}>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em]">§{n}</p>
          <div className="min-w-0">
            <h2
              className={`font-serif font-light leading-[1.02] tracking-[-0.02em] ${heading}`}
              style={{ fontSize: "clamp(2.1rem, min(5vw, 8vh), 4.4rem)" }}
            >
              {title}
            </h2>
            <div className="mt-8">{children}</div>
          </div>
        </div>
      </div>
    </section>
  );
}

const CHAIN = [
  {
    id: "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
    rel: "your from_pretrained line",
    card: "apache-2.0",
  },
  { id: "Xkev/Llama-3.2V-11B-cot", rel: "quantised from", card: "apache-2.0" },
  {
    id: "meta-llama/Llama-3.2-11B-Vision-Instruct",
    rel: "fine-tuned from",
    card: "Llama 3.2 Community License",
  },
];

const AMENDMENT = [
  ["19 Nov 2024", "Xkev/Llama-3.2V-11B-cot is published; the card declares apache-2.0."],
  ["9 Jul 2025", "Discussion #12, “License compatibility”, is opened."],
  ["16 Nov 2025", "LICENSE_llama.txt is uploaded (commit e8c2529775). 130 days."],
  ["Today", "The card still declares apache-2.0. None of its 9 children received the change."],
];

const ENGINE = [
  [
    "a",
    "Many graphs, one instance",
    "A shared hub, one private graph per company, a sandbox per visitor cloned with GRAPH.COPY.",
  ],
  [
    "b",
    "Vectors inside the graph",
    "Weight fingerprints in a cosine index, searched and filtered by graph properties in the same query.",
  ],
  [
    "c",
    "One query, weights to clauses",
    "Sampled weights → nearest parent → trusted ancestry → licences → clauses. A few milliseconds.",
  ],
  [
    "d",
    "Bounded traversal",
    "Every ancestry path to six hops, through merges, at a minimum trust tier; every descendant for the reverse fan-out.",
  ],
  [
    "e",
    "Algorithms in Cypher",
    "WCC unmasks re-uploads, PageRank ranks relabels, betweenness finds chokepoints, label propagation finds families.",
  ],
  [
    "f",
    "Trust on the edges",
    "Tiers, salted confirmations and merge shares read inside the path. Stop FalkorDB and every answer stops.",
  ],
];

const DEFINITIONS = [
  [
    "Weight DNA",
    "1,024 values sampled from two tensors with HTTP range reads, about 2 KB, never the whole file. Same scheme for safetensors and GGUF.",
  ],
  [
    "Tier",
    "Trust in a lineage edge: 0 weak inference, 1 strong inference or weights, 2 declared on the card, 3 confirmed by two companies, 4 confirmed by the author. Strict mode needs 2 or more.",
  ],
  [
    "Ruling",
    "A company's decision about one deployment, append-only, resting on the facts it used. A change upstream reopens it; approving the review supersedes it.",
  ],
  [
    "Sandbox",
    "Your private copy of a fictional company. Everything you click writes there and expires after two hours.",
  ],
  [
    "Hub",
    "The shared graph of public facts. It never stores which company uses which model; confirmations arrive as salted hashes.",
  ],
  [
    "Verdict",
    "Allowed, allowed with obligations, blocked, or cannot determine. Deterministic code over FalkorDB rows; a language model may only phrase it.",
  ],
];

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="-mt-8 -mb-8">
      <RedlineHero />

      <Clause n="2" title={<>Chain of title.</>}>
        <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr]">
          <ol className="relative space-y-6 border-l-2 border-ink pl-6">
            {CHAIN.map((node, idx) => (
              <li key={node.id} className="relative">
                <span className="absolute -left-[33px] top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-ink bg-paper font-mono text-[9px]">
                  {idx}
                </span>
                <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-soft">
                  {node.rel}
                </p>
                <p className="mt-1 break-all font-mono text-sm">{node.id}</p>
                <p className="mt-1 text-sm">
                  card declares{" "}
                  <span className={idx < 2 ? "strike" : "text-redline"}>{node.card}</span>
                </p>
              </li>
            ))}
          </ol>
          <div>
            <p className="font-serif text-2xl italic leading-snug">
              “For the multimodal Llama 3.2 models, the licence rights are not granted to companies
              whose principal place of business is in the European Union.”
            </p>
            <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-soft">
              Clause summary · quoted at runtime from Meta&apos;s official licence text
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <span className="stamp font-mono text-sm text-redline">Blocked · Berlin</span>
              <span
                className="stamp font-mono text-sm text-ink"
                style={{ transform: "rotate(2deg)" }}
              >
                With obligations · New York
              </span>
            </div>
            <p className="mt-6 text-sm text-ink-soft">
              One Cypher query walks every path, through every merge and quantisation, and collects
              each licence&apos;s clauses. 17 ms, end to end.
            </p>
            <Link
              href="/m/OPEA/Llama-3.2V-11B-cot-int4-sym-inc?hq=DE&c=1"
              className="mt-4 inline-block font-medium underline decoration-redline decoration-2 hover:text-redline"
            >
              Open this verdict →
            </Link>
          </div>
        </div>
      </Clause>

      <Clause
        n="3"
        tone="graphite"
        title={
          <>
            Exhibit A: <em className="text-redline">what the weights say.</em>
          </>
        }
      >
        <p className="max-w-2xl text-lg text-muted">
          A card can be wrong. Weights can&apos;t. ModelBrain reads about 2 KB of a model&apos;s
          actual weights, 1,024 values, and compares them in FalkorDB&apos;s vector index.
          Fine-tunes stay close to their parent; independently trained models land near zero.
        </p>
        <SimilarityScale />
        <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
          Each dot is a real measurement · cosine similarity of sampled weights · 18 Oct 2026
        </p>
      </Clause>

      <Clause n="4" title={<>Schedule 1: where metadata and weights disagree.</>}>
        <Schedule />
      </Clause>

      <Clause n="5" tone="paper-2" title={<>Amendment, with no notice served.</>}>
        <div className="grid gap-10 lg:grid-cols-[1.2fr_1fr]">
          <ol className="divide-y divide-ink/15 border-y border-ink/15">
            {AMENDMENT.map(([date, text], idx) => (
              <li key={date} className="grid grid-cols-[110px_1fr] gap-4 py-4">
                <span
                  className={`font-mono text-xs ${idx === 2 ? "text-redline" : "text-ink-soft"}`}
                >
                  {date}
                </span>
                <span className={idx === 3 ? "font-serif text-xl italic" : ""}>{text}</span>
              </li>
            ))}
          </ol>
          <div>
            <p className="font-serif text-2xl leading-snug">
              When something changes upstream, ModelBrain walks every descendant and reopens each
              company decision that rested on one of them, as a review task for the person who owns
              it.
            </p>
            <Link
              href="/replay/xkev"
              className="mt-6 inline-block rounded-sm bg-ink px-5 py-3 font-medium text-paper hover:bg-redline"
            >
              Replay the amendment →
            </Link>
          </div>
        </div>
      </Clause>

      <Clause n="6" title={<>Countersigned by two parties, trusted by all.</>}>
        <div className="grid gap-10 md:grid-cols-2">
          <div>
            <div className="border-b-2 border-ink pb-1 font-serif text-2xl italic">
              Harbor Apps Inc.
            </div>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-soft">
              Signed · fictional company · stored in the hub as a salted hash
            </p>
          </div>
          <div>
            <div className="border-b-2 border-dashed border-redline pb-1 font-serif text-2xl italic text-ink/40">
              your company
            </div>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em] text-redline">
              Sign here · tier 1 → 3 · strict verdict flips
            </p>
          </div>
        </div>
        <p className="mt-8 max-w-2xl text-ink-soft">
          A re-upload declares no parent; its fingerprints say Llama 3.2 1B. A strict company
          refuses inferred lineage until two independent companies confirm the edge. Then it is
          trusted for everyone, and nobody learns who confirmed.
        </p>
        <Link
          href="/hidden-lineage"
          className="mt-4 inline-block font-medium underline decoration-redline decoration-2 hover:text-redline"
        >
          Countersign in your sandbox →
        </Link>
      </Clause>

      <Clause n="7" tone="graphite" title={<>Obligations of the agent.</>}>
        <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr]">
          <div className="space-y-4 font-serif text-xl leading-relaxed">
            <p>
              <span className="font-mono text-sm text-muted">(a)</span> Before calling{" "}
              <code className="font-mono text-base">from_pretrained</code>, the agent shall call{" "}
              <code className="font-mono text-base text-redline">can_i_use</code>.
            </p>
            <p>
              <span className="font-mono text-sm text-muted">(b)</span> Before a pull request is
              merged, the pipeline shall run{" "}
              <code className="font-mono text-base">modelbrain-check</code>.
            </p>
            <p>
              <span className="font-mono text-sm text-muted">(c)</span> Where the weights speak, the
              agent shall ask <code className="font-mono text-base">trace_weights</code>.
            </p>
          </div>
          <div className="rounded-sm border border-white/15 bg-surface p-5 font-mono text-[13px] leading-relaxed">
            <p className="text-muted">
              $ claude &quot;add OPEA/Llama-3.2V-11B-cot-int4-sym-inc for our German product&quot;
            </p>
            <p className="mt-3 text-muted">
              → modelbrain.can_i_use(model_id, hq_country=&quot;DE&quot;)
            </p>
            <p className="mt-1 text-redline">VERDICT: BLOCKED</p>
            <p className="text-text">
              Path: OPEA → Xkev → unsloth mirror → meta-llama/Llama-3.2-11B-Vision-Instruct
            </p>
            <p className="mt-3 text-text">
              &quot;I didn&apos;t add the model, and app.py is unchanged. The licence screen came
              back BLOCKED for Kestrel.&quot;
            </p>
            <p className="mt-3 text-[11px] uppercase tracking-[0.14em] text-muted">
              Excerpt of a recorded Claude Code session against ModelBrain&apos;s MCP server
            </p>
          </div>
        </div>
        <Link
          href="/mcp"
          className="mt-8 inline-block rounded-sm bg-accent px-5 py-3 font-medium text-ink hover:bg-redline hover:text-paper"
        >
          Connect your agent →
        </Link>
      </Clause>

      <Clause n="8" title={<>Governing engine: FalkorDB.</>}>
        <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
          {ENGINE.map(([letter, title, text]) => (
            <div key={letter} className="grid grid-cols-[32px_1fr] gap-2">
              <span className="font-mono text-sm text-redline">({letter})</span>
              <div>
                <p className="font-serif text-2xl">{title}</p>
                <p className="mt-1 text-sm text-ink-soft">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </Clause>

      <Clause n="9" tone="paper-2" title={<>Definitions.</>}>
        <dl className="grid gap-x-10 gap-y-6 md:grid-cols-2">
          {DEFINITIONS.map(([term, text]) => (
            <div key={term} className="border-t border-ink/15 pt-3">
              <dt className="font-serif text-xl">
                <span className="text-ink-soft">“</span>
                {term}
                <span className="text-ink-soft">”</span> means
              </dt>
              <dd className="mt-1 text-sm text-ink-soft">{text}</dd>
            </div>
          ))}
        </dl>
      </Clause>

      <section className="bleed bg-redline text-paper">
        <div className="mx-auto max-w-6xl px-4 py-20 md:py-28">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-paper/80">
            §10 · Execution
          </p>
          <p
            className="mt-4 font-serif font-light leading-[0.95] tracking-[-0.03em]"
            style={{ fontSize: "clamp(3rem, min(9vw, 14vh), 8rem)" }}
          >
            Sign nothing
            <br />
            you haven&apos;t traced.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link
              href="/#check"
              className="rounded-sm bg-paper px-6 py-3 font-medium text-ink hover:bg-ink hover:text-paper"
            >
              Check a model
            </Link>
            <code className="rounded-sm border border-paper/40 px-4 py-3 font-mono text-sm">
              claude mcp add --transport http modelbrain {API}/mcp
            </code>
          </div>
        </div>
      </section>
    </main>
  );
}
