"use client";

import { useState } from "react";

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
    <main className="[overflow-wrap:anywhere]">
      <h1 className="text-3xl">Use ModelBrain from your coding agent</h1>
      <p className="mt-2 max-w-3xl text-muted">
        ModelBrain is an MCP server. Your agent calls it before it writes{" "}
        <code className="font-mono">from_pretrained</code>, and gets the verdict, the lineage path
        and the clause straight from FalkorDB.
      </p>

      <section className="mt-6">
        <h2 className="text-xl">Claude Code</h2>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <pre className="overflow-x-auto rounded bg-surface p-3 text-sm" data-testid="mcp-command">
            {command}
          </pre>
          <button
            type="button"
            className="rounded border border-white/10 px-3 py-2 text-sm text-accent"
            onClick={() => copy(command, "claude")}
          >
            {copied === "claude" ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="mt-2 text-sm text-muted">
          Then ask: &quot;add OPEA/Llama-3.2V-11B-cot-int4-sym-inc to our pipeline for our German
          product&quot;. The agent calls <code className="font-mono">can_i_use</code> and reports
          BLOCKED with the path.
        </p>
      </section>

      <section className="mt-6">
        <h2 className="text-xl">Cursor and other MCP clients</h2>
        <div className="mt-2 flex flex-wrap items-start gap-2">
          <pre className="overflow-x-auto rounded bg-surface p-3 text-sm">{cursor}</pre>
          <button
            type="button"
            className="rounded border border-white/10 px-3 py-2 text-sm text-accent"
            onClick={() => copy(cursor, "cursor")}
          >
            {copied === "cursor" ? "Copied" : "Copy"}
          </button>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xl">Tools</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm" data-testid="mcp-tools">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-2 pr-4">Tool</th>
                <th className="py-2 pr-4">What it answers</th>
              </tr>
            </thead>
            <tbody>
              {TOOLS.map(([name, text]) => (
                <tr key={name} className="border-t border-white/10">
                  <td className="py-2 pr-4 font-mono">{name}</td>
                  <td className="py-2 pr-4">{text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xl">In CI</h2>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          The <code className="font-mono">actions/modelbrain-check</code> GitHub Action scans a pull
          request for Hugging Face model ids, asks the same graph, writes a job summary with path
          and blocking clauses, and fails the check when a model is BLOCKED for your headquarters.
        </p>
      </section>

      <p className="mt-10 text-sm text-muted">Automated screening, not legal advice.</p>
    </main>
  );
}
