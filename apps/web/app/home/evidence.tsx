"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const BASE = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function useInView<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return { ref, seen };
}

// Real measurements (cosine similarity of sampled weights), 18 Oct 2026.
const POINTS = [
  { v: -0.006, label: "TinyLlama vs Llama 3.2 1B", kind: "unrelated" },
  { v: 0.022, label: "Same model, different layer", kind: "unrelated" },
  { v: 0.56, label: "Qwen2.5-Coder vs Qwen2.5 (continued training)", kind: "related" },
  { v: 0.84, label: "Bielik-7B vs Mistral 7B", kind: "related" },
  { v: 0.9918, label: "Llama 3.2 1B Instruct vs base", kind: "derived" },
  { v: 0.9995, label: "A grammar fine-tune vs its base", kind: "derived" },
  { v: 1.0, label: "Re-upload with a new card", kind: "derived" },
];

export function SimilarityScale() {
  const { ref, seen } = useInView<HTMLDivElement>();
  const x = (v: number) => `${((v + 0.1) / 1.1) * 100}%`;
  return (
    <div ref={ref} className="mt-12">
      <div className="relative h-56">
        <div className="absolute left-0 right-0 top-24 h-px bg-white/25" />
        <div className="absolute top-20 h-8 w-px bg-white/40" style={{ left: x(0.6) }} />
        <p
          className="absolute top-36 -translate-x-1/2 font-mono text-[11px] uppercase tracking-[0.14em] text-redline"
          style={{ left: x(0.6) }}
        >
          tier 1 at 0.60
        </p>
        {POINTS.map((p, idx) => (
          <div
            key={p.label}
            className="absolute top-24 -translate-x-1/2 -translate-y-1/2"
            style={{
              left: seen ? x(p.v) : x(0.45),
              opacity: seen ? 1 : 0,
              transition: `left 1100ms cubic-bezier(0.2,0.7,0.2,1) ${idx * 90}ms, opacity 400ms ${idx * 90}ms`,
            }}
          >
            <span
              className={`block h-3.5 w-3.5 rounded-full border-2 ${
                p.kind === "derived"
                  ? "border-redline bg-redline"
                  : p.kind === "related"
                    ? "border-text bg-bg"
                    : "border-muted bg-bg"
              }`}
            />
            <span
              className={`absolute left-1/2 w-36 -translate-x-1/2 text-center text-[11px] leading-tight text-muted ${
                idx % 2 ? "top-6" : "bottom-6"
              }`}
            >
              {p.v < 0.99 ? (
                <>
                  {p.label}
                  <span className="block font-mono text-text">{p.v.toFixed(3)}</span>
                </>
              ) : null}
            </span>
          </div>
        ))}
        <p className="absolute left-0 top-48 font-mono text-[11px] text-muted">−0.1 unrelated</p>
        <p className="absolute right-0 top-48 font-mono text-[11px] text-muted">1.0 same weights</p>
      </div>
      <div className="ml-auto max-w-sm border-l-2 border-redline pl-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-redline">
          Derived · 0.99 to 1.0
        </p>
        <ul className="mt-2 space-y-1 text-sm text-muted">
          {POINTS.filter((p) => p.v >= 0.99).map((p) => (
            <li key={p.label} className="flex justify-between gap-4">
              <span>{p.label}</span>
              <span className="font-mono text-text">{p.v.toFixed(4)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

type Hidden = {
  model: string;
  card_license: string | null;
  weights_parent: string;
  score: number | null;
  share: number | null;
  root: string | null;
  root_license: string | null;
};

const RESTRICTIVE = /^(llama|gemma|other|cc-by-nc|qwen|deepseek|agpl)/i;
const FALLBACK = { fingerprinted: 381, undeclared: 169, restrictive: 119 };

export function Schedule() {
  const [rows, setRows] = useState<Hidden[] | null>(null);
  const [counts, setCounts] = useState(FALLBACK);
  const [live, setLive] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch(`${BASE()}/api/dna/hidden?limit=500`).then((r) => (r.ok ? r.json() : Promise.reject())),
      fetch(`${BASE()}/api/dna/coverage`).then((r) => (r.ok ? r.json() : Promise.reject())),
    ])
      .then(([hidden, coverage]: [Hidden[], { by_status: Record<string, number> }]) => {
        const singles = hidden.filter((r) => r.share === null);
        const models = new Set(singles.map((r) => r.model));
        const restrictive = singles.filter((r) => RESTRICTIVE.test(r.root_license ?? ""));
        // Lead with the clearest cases: a permissive card over restrictive weights.
        const PERMISSIVE = /^(apache-2\.0|mit|wtfpl|bsd|cc-by-4\.0|cc-by-sa|unlicense)/i;
        const strong = restrictive.filter((r) => PERMISSIVE.test(r.card_license ?? ""));
        setRows(strong.slice(0, 7));
        setCounts({
          fingerprinted: coverage.by_status.OK ?? FALLBACK.fingerprinted,
          undeclared: models.size,
          restrictive: new Set(restrictive.map((r) => r.model)).size,
        });
        setLive(true);
      })
      .catch(() => setRows([]));
  }, []);

  return (
    <div>
      <div className="grid gap-px overflow-hidden rounded-sm bg-ink/15 sm:grid-cols-3">
        {[
          [counts.fingerprinted, "models fingerprinted from their weights"],
          [counts.undeclared, "match a parent their card does not declare"],
          [counts.restrictive, "of those trace to a licence with conditions"],
        ].map(([n, label]) => (
          <div key={String(label)} className="bg-paper p-6">
            <p
              className="font-serif font-light leading-none tracking-[-0.03em] text-ink"
              style={{ fontSize: "clamp(3.4rem, 8vw, 6.5rem)" }}
            >
              {n}
            </p>
            <p className="mt-2 max-w-[16rem] text-sm text-ink-soft">{label}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-soft">
        {live ? "Live from the graph" : "As of 18 Oct 2026 (graph not reachable)"}
      </p>

      <div className="mt-10 overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b-2 border-ink font-mono text-[11px] uppercase tracking-[0.12em] text-ink-soft">
              <th className="py-2 pr-4 font-normal">Item</th>
              <th className="py-2 pr-4 font-normal">Model</th>
              <th className="py-2 pr-4 font-normal">Card declares</th>
              <th className="py-2 pr-4 font-normal">Weights trace to</th>
              <th className="py-2 pr-4 font-normal">Similarity</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map((row, idx) => (
              <tr key={row.model} className="border-b border-ink/15 align-top">
                <td className="py-3 pr-4 font-mono text-xs text-ink-soft">1.{idx + 1}</td>
                <td className="py-3 pr-4 font-mono text-xs">
                  <a
                    className="hover:text-redline"
                    href={`https://huggingface.co/${row.model}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {row.model}
                  </a>
                </td>
                <td className="py-3 pr-4">
                  <span className="strike" style={{ ["--strike" as string]: 1 }}>
                    {row.card_license}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className="text-redline">{row.root_license}</span>
                  <span className="block font-mono text-[11px] text-ink-soft">{row.root}</span>
                </td>
                <td className="py-3 pr-4 font-mono text-xs">{row.score?.toFixed(4)}</td>
              </tr>
            ))}
            {rows !== null && rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-4 text-ink-soft">
                  The schedule loads from the live graph. Start the API to see it.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Link
        href="/findings"
        className="mt-6 inline-block font-medium underline decoration-redline decoration-2 hover:text-redline"
      >
        Read the full schedule →
      </Link>
      <p className="mt-2 text-xs text-ink-soft">
        Many cards explain lineage in prose; these rows are about the machine-readable metadata.
        Every row links to the Hub so anyone can check it.
      </p>
    </div>
  );
}
