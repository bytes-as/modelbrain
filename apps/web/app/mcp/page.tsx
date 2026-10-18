"use client";

import { useState } from "react";

import { Disclaimer, Exhibit, ExhibitHeader, Part } from "../components/exhibit";

const TOOLS: [string, string][] = [
  [
    "can_i_use",
    "Verdict for a model given HQ country, markets and commercial use, with path and clause.",
  ],
  [
    "trace_weights",
    "The true parent from ~2 KB of sampled weights, merges, and the obligations the weights carry.",
  ],
  ["explain", "Every ancestry path, the clauses with quotes and sources, and trust tiers."],
  ["lineage", "Ancestors and descendants with declared licences and trust tiers."],
  ["proof_path", "Shortest derivation path to a given base model, or proof that none exists."],
  [
    "relabel_hubs",
    "PageRank over lineage: models whose card is permissive but whose ancestors are not.",
  ],
  ["chokepoints", "Betweenness: models where a licence fix reaches the most descendants."],
  ["families", "Label propagation: model families in the lineage graph."],
  [
    "confirm_edge",
    "A company confirms a lineage edge; two independent confirmations raise its trust tier.",
  ],
  ["watch", "Subscribe a company to upstream changes; a change reopens its rulings."],
];

export default function McpPage() {
  const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const command = `claude mcp add --transport http modelbrain ${api}/mcp`;
  const cursor = JSON.stringify({ mcpServers: { modelbrain: { url: `${api}/mcp` } } }, null, 2);
  const [copied, setCopied] = useState("");

  function copy(text: string, which: string) {
    navigator.clipboard
      ?.writeText(text)
      .then(() => setCopied(which))
      .catch(() => setCopied(""));
  }

  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit F · Obligations of the agent"
        source="MCP server · HTTP transport"
        title={
          <>
            The agent shall call <span className="font-mono text-[0.8em]">can_i_use</span> before{" "}
            <span className="font-mono text-[0.8em]">from_pretrained</span>.
          </>
        }
        lede={
          <>
            ModelBrain is an MCP server. Your agent calls it before it writes from_pretrained, and
            gets the verdict, the lineage path and the clause straight from FalkorDB.
          </>
        }
      />

      <Part n="1" title="Claude Code">
        <Code
          caption="claude mcp add · one command"
          testId="mcp-command"
          copied={copied === "claude"}
          onCopy={() => copy(command, "claude")}
        >
          {command}
        </Code>
        <p className="mt-5 max-w-3xl font-serif text-xl leading-relaxed">
          Then ask: &quot;add OPEA/Llama-3.2V-11B-cot-int4-sym-inc to our pipeline for our German
          product&quot;. The agent calls <code className="font-mono text-base">can_i_use</code> and
          reports <span className="font-mono text-base text-redline">BLOCKED</span> with the path.
        </p>
      </Part>

      <Part n="2" title="Cursor and other MCP clients">
        <Code
          caption="mcp.json · mcpServers"
          copied={copied === "cursor"}
          onCopy={() => copy(cursor, "cursor")}
        >
          {cursor}
        </Code>
      </Part>

      <Part n="3" title="Tools" note={`${TOOLS.length} tools, each answered by one graph query.`}>
        <div className="ledger-wrap">
          <table className="ledger" data-testid="mcp-tools">
            <thead>
              <tr>
                <th>Tool</th>
                <th>What it answers</th>
              </tr>
            </thead>
            <tbody>
              {TOOLS.map(([name, text]) => (
                <tr key={name}>
                  <td className="whitespace-nowrap font-mono text-[13px]">{name}</td>
                  <td className="min-w-[14rem] text-muted">{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Part>

      <Part n="4" title="In CI">
        <p className="max-w-3xl font-serif text-xl leading-relaxed">
          <span className="font-mono text-sm text-muted">(b)</span> The{" "}
          <code className="font-mono text-base">actions/modelbrain-check</code> GitHub Action scans
          a pull request for Hugging Face model ids, asks the same graph, writes a job summary with
          path and blocking clauses, and fails the check when a model is{" "}
          <span className="font-mono text-base text-redline">BLOCKED</span> for your headquarters.
        </p>
      </Part>

      <Disclaimer />
    </Exhibit>
  );
}

function Code({
  caption,
  children,
  testId,
  copied,
  onCopy,
}: {
  caption: string;
  children: string;
  testId?: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <figure className="min-w-0">
      <figcaption className="flex items-baseline justify-between gap-3 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
        <span>{caption}</span>
        <button
          type="button"
          onClick={onCopy}
          className="font-mono text-xs uppercase tracking-[0.12em] text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </figcaption>
      <pre
        className="mt-2 overflow-x-auto border border-white/10 bg-surface p-4 font-mono text-[13px] leading-relaxed text-text"
        data-testid={testId}
      >
        {children}
      </pre>
    </figure>
  );
}
