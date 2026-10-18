"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Hidden = {
  model: string;
  card_license: string | null;
  format: string | null;
  weights_parent: string;
  score: number | null;
  share: number | null;
  root: string | null;
  root_license: string | null;
};

type Conflict = {
  model: string;
  declared_parent: string;
  weights_parent: string;
  sim: number;
  declared_sim: number | null;
  reason: string;
};

// Licences with conditions that a permissive card label would hide.
const RESTRICTIVE = /^(llama|gemma|other|cc-by-nc|qwen|deepseek|agpl)/i;

function severity(row: Hidden): number {
  const card = (row.card_license ?? "").toLowerCase();
  const root = (row.root_license ?? "").toLowerCase();
  let score = 0;
  if (RESTRICTIVE.test(root)) score += 2;
  if (card && root && card !== root) score += 1;
  return score;
}

type Coverage = { total: number; by_status: Record<string, number> };

const HUB = "https://huggingface.co";

function ModelLink({ id }: { id: string }) {
  const [owner, name] = id.split("/");
  return (
    <span className="whitespace-nowrap">
      <Link className="text-accent" href={`/m/${owner}/${name}`}>
        {id}
      </Link>{" "}
      <a className="text-xs text-muted" href={`${HUB}/${id}`} target="_blank" rel="noreferrer">
        Hub ↗
      </a>
    </span>
  );
}

export default function FindingsPage() {
  const [hidden, setHidden] = useState<Hidden[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [state, setState] = useState<"loading" | "done" | "error">("loading");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    Promise.all([
      fetch(`${base}/api/dna/hidden?limit=200`).then((r) => (r.ok ? r.json() : Promise.reject())),
      fetch(`${base}/api/dna/conflicts?limit=100`).then((r) =>
        r.ok ? r.json() : Promise.reject(),
      ),
      fetch(`${base}/api/dna/coverage`).then((r) => (r.ok ? r.json() : Promise.reject())),
    ])
      .then(([h, c, cov]) => {
        setHidden(h as Hidden[]);
        setConflicts(c as Conflict[]);
        setCoverage(cov as Coverage);
        setState("done");
      })
      .catch(() => setState("error"));
  }, []);

  const singles = hidden
    .filter((row) => row.share === null)
    .sort((a, b) => severity(b) - severity(a) || (b.score ?? 0) - (a.score ?? 0));
  const [showAll, setShowAll] = useState(false);
  const important = singles.filter((row) => severity(row) >= 2);
  const shown = showAll ? singles : important.length > 0 ? important : singles;
  const merges = hidden.filter((row) => row.share !== null);
  const ok = coverage?.by_status.OK ?? 0;
  const gated = coverage?.by_status.GATED ?? 0;
  const quantized =
    (coverage?.by_status.QUANTIZED ?? 0) + (coverage?.by_status.UNSUPPORTED_ARCH ?? 0);

  return (
    <main className="[overflow-wrap:anywhere]">
      <h1 className="text-3xl">Where metadata and weights disagree</h1>
      <p className="mt-2 max-w-3xl text-muted">
        We read about 2 KB of each model&apos;s actual weight values with HTTP range requests and
        compare them in FalkorDB&apos;s vector index. A close match means the parent&apos;s
        obligations may apply, whatever the model card declares. Many cards explain their lineage in
        prose; these rows are about the machine-readable metadata.
      </p>
      {coverage ? (
        <p className="mt-3 text-sm text-muted" data-testid="dna-coverage">
          Fingerprinted {ok} of {coverage.total} models; {gated} gated; {quantized} in formats we
          don&apos;t sample yet.
        </p>
      ) : null}
      {state === "loading" ? <p className="mt-6 text-muted">Loading findings…</p> : null}
      {state === "error" ? (
        <p className="mt-6 text-[#f0605a]">Could not load findings. FalkorDB may be unavailable.</p>
      ) : null}

      <section className="mt-8">
        <h2 className="text-xl">Weights match a parent the card does not declare</h2>
        {state === "done" && singles.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No findings yet. Run the fingerprint crawl.</p>
        ) : null}
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm" data-testid="findings-hidden">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-2 pr-4">Model</th>
                <th className="py-2 pr-4">Card licence</th>
                <th className="py-2 pr-4">Weights parent</th>
                <th className="py-2 pr-4">Similarity</th>
                <th className="py-2 pr-4">Root</th>
                <th className="py-2 pr-4">Root licence</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => (
                <tr key={`${row.model}-${row.weights_parent}`} className="border-t border-white/10">
                  <td className="py-2 pr-4">
                    <ModelLink id={row.model} />
                  </td>
                  <td className="py-2 pr-4">{row.card_license ?? "none"}</td>
                  <td className="py-2 pr-4">
                    <ModelLink id={row.weights_parent} />
                  </td>
                  <td className="py-2 pr-4 font-mono">{row.score?.toFixed(3) ?? "?"}</td>
                  <td className="py-2 pr-4">{row.root ?? "unknown"}</td>
                  <td className="py-2 pr-4">{row.root_license ?? "unknown"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {singles.length > shown.length || showAll ? (
          <button
            type="button"
            className="mt-3 text-sm text-accent"
            onClick={() => setShowAll(!showAll)}
            data-testid="toggle-all"
          >
            {showAll
              ? "Show only restrictive-licence findings"
              : `Show all ${singles.length} (including ${singles.length - shown.length} with permissive roots)`}
          </button>
        ) : null}
      </section>

      <section className="mt-10">
        <h2 className="text-xl">Declared parent and weights disagree</h2>
        {state === "done" && conflicts.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            No disagreements found in the fingerprinted set.
          </p>
        ) : null}
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm" data-testid="findings-conflicts">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-2 pr-4">Model</th>
                <th className="py-2 pr-4">Declared parent</th>
                <th className="py-2 pr-4">Weights parent</th>
                <th className="py-2 pr-4">Similarity</th>
              </tr>
            </thead>
            <tbody>
              {conflicts.map((row) => (
                <tr key={row.model} className="border-t border-white/10">
                  <td className="py-2 pr-4">
                    <ModelLink id={row.model} />
                  </td>
                  <td className="py-2 pr-4">
                    <ModelLink id={row.declared_parent} />
                  </td>
                  <td className="py-2 pr-4">
                    <ModelLink id={row.weights_parent} />
                  </td>
                  <td className="py-2 pr-4 font-mono">
                    {row.sim.toFixed(3)}
                    {row.declared_sim !== null ? ` vs ${row.declared_sim.toFixed(3)} declared` : ""}
                    <span className="block font-sans text-xs text-muted">{row.reason}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {merges.length > 0 ? (
        <section className="mt-10">
          <h2 className="text-xl">Merges recovered from the weights</h2>
          <ul className="mt-3 space-y-2 text-sm" data-testid="findings-merges">
            {merges.map((row) => (
              <li key={`${row.model}-${row.weights_parent}`}>
                <ModelLink id={row.model} />: {Math.round((row.share ?? 0) * 100)}% of sampled
                weights from <ModelLink id={row.weights_parent} />
                {row.root_license ? ` (root licence ${row.root_license})` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="mt-10 text-sm text-muted">Automated screening, not legal advice.</p>
    </main>
  );
}
