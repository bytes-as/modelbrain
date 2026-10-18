"use client";

import { useEffect, useState } from "react";

import {
  Disclaimer,
  Exhibit,
  ExhibitHeader,
  Licence,
  ModelRef,
  Part,
  Status,
  Tag,
  TextButton,
} from "../components/exhibit";

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

export default function FindingsPage() {
  const [hidden, setHidden] = useState<Hidden[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const [showAll, setShowAll] = useState(false);

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
  const important = singles.filter((row) => severity(row) >= 2);
  const shown = showAll ? singles : important.length > 0 ? important : singles;
  const merges = hidden.filter((row) => row.share !== null);
  const ok = coverage?.by_status.OK ?? 0;
  const gated = coverage?.by_status.GATED ?? 0;
  const quantized =
    (coverage?.by_status.QUANTIZED ?? 0) + (coverage?.by_status.UNSUPPORTED_ARCH ?? 0);
  const dash = state === "done" ? 0 : "–";

  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit A · Weight DNA"
        source="Live from FalkorDB · vector index, cosine"
        title={
          <>
            Where the metadata and <em className="text-redline">the weights</em> disagree.
          </>
        }
        lede="We read about 2 KB of each model's real weight values with HTTP range requests and compare them in FalkorDB's vector index. A close match means the parent's obligations may apply, whatever the card declares. Many cards explain lineage in prose; these rows are about the machine-readable metadata."
        facts={[
          { value: coverage ? ok : "–", label: `Fingerprinted of ${coverage?.total ?? "–"}` },
          { value: singles.length || dash, label: "Undeclared parents" },
          { value: important.length || dash, label: "Restrictive root" },
          { value: conflicts.length || dash, label: "Declared parent contradicted" },
        ]}
      >
        {coverage ? (
          <p className="mt-4 font-mono text-[11px] text-ink-soft" data-testid="dna-coverage">
            Fingerprinted {ok} of {coverage.total} models; {gated} gated; {quantized} in formats we
            don&apos;t sample yet.
          </p>
        ) : null}
      </ExhibitHeader>

      <div className="pt-6">
        <Status state={state === "loading" ? "loading" : state === "error" ? "error" : "done"} />
      </div>

      <Part
        n="1"
        title="Weights match a parent the card does not declare"
        note={
          showAll
            ? "Every undeclared parent, most severe first."
            : "Rows whose root carries conditions a permissive card label would hide. The card's licence is struck where the root's terms differ."
        }
      >
        <Status
          state={state === "done" && singles.length === 0 ? "empty" : "done"}
          empty="No findings yet. Run the fingerprint crawl."
        />
        <div className="ledger-wrap">
          <table className="ledger min-w-[880px]" data-testid="findings-hidden">
            <thead>
              <tr>
                <th>Model</th>
                <th>Card says</th>
                <th>Weights parent</th>
                <th className="num">Cosine</th>
                <th>Root · licence</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => {
                const contradicted = severity(row) >= 2 && row.card_license !== row.root_license;
                return (
                  <tr key={`${row.model}-${row.weights_parent}`}>
                    <td className="w-[30%]">
                      <ModelRef id={row.model} />
                      {row.format === "gguf" ? (
                        <span className="ml-2">
                          <Tag>GGUF</Tag>
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <Licence name={row.card_license} struck={contradicted} />
                    </td>
                    <td className="w-[30%]">
                      <ModelRef id={row.weights_parent} />
                    </td>
                    <td className="num">{row.score?.toFixed(3) ?? "?"}</td>
                    <td>
                      <span className="block break-all font-mono text-[13px] text-muted">
                        {row.root ?? "unknown"}
                      </span>
                      <span
                        className={`font-mono text-[13px] ${contradicted ? "text-redline" : "text-text"}`}
                      >
                        {row.root_license ?? "unknown"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {singles.length > shown.length || showAll ? (
          <TextButton onClick={() => setShowAll(!showAll)} testId="toggle-all">
            {showAll
              ? "Show only restrictive-licence findings"
              : `Show all ${singles.length} (including ${singles.length - shown.length} with permissive roots)`}
          </TextButton>
        ) : null}
      </Part>

      <Part
        n="2"
        title="The declared parent and the weights disagree"
        note="The card names a base model; the sampled weights sit measurably closer to another."
      >
        <Status
          state={state === "done" && conflicts.length === 0 ? "empty" : "done"}
          empty="No disagreements found in the fingerprinted set."
        />
        <div className="ledger-wrap">
          <table className="ledger min-w-[880px]" data-testid="findings-conflicts">
            <thead>
              <tr>
                <th>Model</th>
                <th>Card declares</th>
                <th>Weights say</th>
                <th className="num">Cosine</th>
              </tr>
            </thead>
            <tbody>
              {conflicts.map((row) => (
                <tr key={row.model}>
                  <td className="w-[28%]">
                    <ModelRef id={row.model} />
                  </td>
                  <td className="w-[28%]">
                    <span className="strike text-muted">
                      <ModelRef id={row.declared_parent} hub={false} />
                    </span>
                  </td>
                  <td className="w-[28%]">
                    <ModelRef id={row.weights_parent} />
                    <span className="mt-1 block text-xs text-muted">{row.reason}</span>
                  </td>
                  <td className="num">
                    {row.sim.toFixed(3)}
                    {row.declared_sim !== null ? (
                      <span className="block text-xs text-muted">
                        vs {row.declared_sim.toFixed(3)}
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Part>

      {merges.length > 0 ? (
        <Part
          n="3"
          title="Merges recovered from the weights"
          note="Least-squares fit of two parents to the sampled weights; accepted only when one parent cannot explain them."
        >
          <ul data-testid="findings-merges">
            {merges.map((row) => (
              <li
                key={`${row.model}-${row.weights_parent}`}
                className="grid gap-2 border-t border-white/10 py-4 md:grid-cols-[minmax(0,1fr)_120px_minmax(0,1fr)]"
              >
                <ModelRef id={row.model} />
                <span className="font-mono text-[13px] text-accent md:text-right">
                  {Math.round((row.share ?? 0) * 100)}% from
                </span>
                <span>
                  <ModelRef id={row.weights_parent} />
                  {row.root_license ? (
                    <span className="block font-mono text-xs text-muted">
                      root licence {row.root_license}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </Part>
      ) : null}

      <Disclaimer />
    </Exhibit>
  );
}
