"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { HostedPanel } from "./hosted-panel";

type Hit = {
  clause_id: string;
  summary: string;
  quote: string | null;
  source_url: string;
  section: string;
  path: string[];
  status?: string;
  license?: string | null;
  edge_tiers?: number[];
};

type Verdict = {
  verdict: string;
  declared_license: string | null;
  declared_differs: boolean;
  inherited_licenses: string[];
  blocking: Hit[];
  obligations: Hit[];
  needs_counsel: Hit[];
  explanation: string;
  disclaimer: string;
  incomplete_reasons: string[];
  alternatives: { model_id: string; verdict: string }[];
  alternatives_message?: string | null;
  cypher?: { q1: string; q2: string };
  computed_ms?: number;
  paths?: PathRow[];
};

type PathRow = {
  path: string[];
  tiers: number[];
  relations: string[];
  methods?: (string | null)[];
  weights_sims?: (number | null)[];
  shares?: (number | null)[];
};

type Exposure = { root: string; is_root: boolean; root_license: string | null; exposure: number };

type Inherits = {
  ms: number;
  cypher: string;
  rows: {
    weights_parent: string;
    sim: number;
    path: string[];
    license: string;
    clauses: string[];
  }[];
};

function edgeChip(row: PathRow | undefined, index: number, parent: string): string | null {
  if (!row) return null;
  const method = row.methods?.[index] ?? null;
  const sim = row.weights_sims?.[index] ?? null;
  const share = row.shares?.[index] ?? null;
  if (method === "weights_merge" && share !== null) {
    return `Merge · ${Math.round(share * 100)}% of sampled weights from ${parent}`;
  }
  if (method === "weights" && sim !== null) {
    return `Weights match ${parent} · similarity ${sim.toFixed(3)}`;
  }
  if (sim !== null) {
    return `Declared · confirmed by weights ${sim.toFixed(3)}`;
  }
  return null;
}

const COLOUR: Record<string, string> = {
  ALLOWED: "#2fbf71",
  ALLOWED_WITH_OBLIGATIONS: "#e9b450",
  BLOCKED: "#f0605a",
  CANNOT_DETERMINE: "#9aa3ae",
};

export function VerdictView({
  modelId,
  hq,
  commercial,
}: {
  modelId: string;
  hq: string;
  commercial: boolean;
}) {
  const [state, setState] = useState<"loading" | "queued" | "done" | "error">("loading");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<string[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [exposure, setExposure] = useState<Exposure[]>([]);
  const [inherits, setInherits] = useState<Inherits | null>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const controller = new AbortController();
    setState("loading");
    setProgress([]);
    setError("");

    async function load() {
      const response = await fetch(`${base}/api/verdict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_id: modelId,
          context: { hq_country: hq, commercial, markets: [hq] },
        }),
        signal: controller.signal,
      });
      const body = await response.json();
      if (response.status === 202 && body.status === "QUEUED" && body.events_url) {
        setState("queued");
        const eventsUrl = body.events_url.startsWith("http")
          ? body.events_url
          : `${base}${body.events_url}`;
        await followEvents(eventsUrl);
        if (controller.signal.aborted) return;
        return load();
      }
      if (!response.ok) {
        setError(body.error?.message || "The check failed.");
        setState("error");
        return;
      }
      setVerdict(body);
      setState("done");
      const merged = ((body.paths ?? []) as PathRow[]).some((row) =>
        row.methods?.includes("weights_merge"),
      );
      const byWeights = ((body.paths ?? []) as PathRow[]).some((row) =>
        (row.methods ?? []).some((m) => m === "weights" || m === "weights_merge"),
      );
      if (byWeights) {
        fetch(`${base}/api/dna/inherits/${modelId}`, { signal: controller.signal })
          .then((r) => (r.ok ? r.json() : null))
          .then((data: Inherits | null) => setInherits(data))
          .catch(() => setInherits(null));
      }
      if (merged) {
        fetch(`${base}/api/dna/exposure/${modelId}`, { signal: controller.signal })
          .then((r) => (r.ok ? r.json() : []))
          .then((rows: Exposure[]) => setExposure(rows))
          .catch(() => setExposure([]));
      }
    }

    async function followEvents(url: string) {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          try {
            const event = JSON.parse(line.slice(6)) as { type?: string; id?: string };
            if (event.type === "node" && event.id) {
              setProgress((prev) => [...prev, `Ingested ${event.id}`]);
            }
            if (event.type === "done" || event.type === "error") return;
          } catch {
            /* ignore malformed SSE */
          }
        }
      }
    }

    load().catch(() => {
      if (!controller.signal.aborted) {
        setError("The API is not reachable.");
        setState("error");
      }
    });
    return () => controller.abort();
  }, [modelId, hq, commercial]);

  const flip = hq === "US" ? "DE" : "US";
  const [owner, name] = modelId.split("/");

  if (state === "loading") {
    return (
      <p
        role="status"
        className="pt-10 font-mono text-xs uppercase tracking-[0.12em] text-muted"
        data-testid="verdict-loading"
      >
        Following the model&apos;s ancestry in FalkorDB…
      </p>
    );
  }
  if (state === "queued") {
    return (
      <div className="space-y-3 pt-10" data-testid="verdict-queued">
        <p role="status" className="font-mono text-xs uppercase tracking-[0.12em] text-muted">
          Ingesting ancestry…
        </p>
        <ul className="break-all font-mono text-xs text-muted">
          {progress.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
    );
  }
  if (state === "error" || !verdict) {
    return (
      <p
        role="alert"
        className="pt-10 font-mono text-xs uppercase tracking-[0.12em] text-redline"
        data-testid="verdict-error"
      >
        {error} Try again from the check page.
      </p>
    );
  }

  const label = verdict.verdict.replaceAll("_", " ");
  const cards = [...verdict.blocking, ...verdict.needs_counsel, ...verdict.obligations];
  // Show the deepest ancestry path (it carries the weight evidence), else the first clause path.
  const deepest = [...(verdict.paths ?? [])].sort((a, b) => b.path.length - a.path.length)[0];
  const path =
    deepest && deepest.path.length > 1 ? deepest.path : (cards[0]?.path ?? deepest?.path ?? []);
  const pathRow = verdict.paths?.find((row) => row.path.join(">") === path.join(">"));
  const hasMerge = (verdict.paths ?? []).some((row) => row.methods?.includes("weights_merge"));

  return (
    <div className="space-y-8 pt-10" data-testid="verdict-done">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <p
          className="stamp font-mono text-xl md:text-2xl"
          data-testid="verdict-badge"
          style={{ color: COLOUR[verdict.verdict] ?? "#9aa3ae" }}
        >
          {label}
        </p>
        <p
          className="min-w-0 font-serif text-2xl leading-snug [overflow-wrap:anywhere] md:text-3xl"
          data-testid="declared-differs"
        >
          The card says{" "}
          {verdict.declared_differs ? (
            <span className="strike">{verdict.declared_license ?? "nothing"}</span>
          ) : (
            <span>{verdict.declared_license ?? "nothing"}</span>
          )}
          .{" "}
          {verdict.inherited_licenses.length ? (
            <>
              The lineage carries{" "}
              <em className={verdict.declared_differs ? "text-redline" : ""}>
                {verdict.inherited_licenses.join(", ")}
              </em>
              .
            </>
          ) : null}
        </p>
      </div>
      <p
        className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted"
        data-testid="context-chips"
      >
        Context: {hq}, {commercial ? "commercial" : "non-commercial"}.{" "}
        <Link
          className="ml-2 text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent"
          data-testid="flip-hq"
          href={`/m/${owner}/${name}?hq=${flip}&c=${commercial ? "1" : "0"}`}
        >
          Flip HQ to {flip}
        </Link>
      </p>
      {path.length > 0 ? (
        <section>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Chain of title
          </p>
          <ol
            className="mt-3 flex flex-wrap items-center gap-2 font-mono text-xs"
            data-testid="lineage-path"
          >
            {path.map((id, index) => {
              const chip = index > 0 ? edgeChip(pathRow, index - 1, id) : null;
              return (
                <li key={id} className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
                  {index > 0 ? <span className="text-muted">→</span> : null}
                  {chip ? (
                    <span
                      className="border border-accent/40 px-2 py-1 font-sans text-accent"
                      data-testid="weights-chip"
                      title="We compared a small sample of the actual weight values (about 2 KB). The model card does not declare this parent."
                    >
                      {chip}
                    </span>
                  ) : null}
                  <span className="min-w-0 break-all border border-white/10 bg-surface px-2 py-1">
                    {id}
                  </span>
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}
      {hasMerge && exposure.length > 0 ? (
        <ul className="text-sm text-muted [overflow-wrap:anywhere]" data-testid="weights-exposure">
          {exposure.map((row) => (
            <li key={row.root}>
              About {Math.round(row.exposure * 100)}% of the sampled weights trace to {row.root}
              {row.root_license ? ` (${row.root_license})` : ""}.
            </li>
          ))}
        </ul>
      ) : null}
      {inherits && inherits.rows.length > 0 ? (
        <section className="border-t border-white/15 pt-5 text-sm" data-testid="weights-inherits">
          <h2 className="font-serif text-2xl font-light leading-tight">
            What the weights carry, in one FalkorDB query
          </h2>
          <p className="mt-2 max-w-3xl text-muted [overflow-wrap:anywhere]">
            Vector search over the sampled weights found {inherits.rows[0].weights_parent}{" "}
            (similarity {inherits.rows[0].sim.toFixed(3)}), then the same query walked its trusted
            ancestry to the licences and clauses: {inherits.ms} ms.
          </p>
          <div className="ledger-wrap mt-4">
            <table className="ledger">
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Licence</th>
                  <th className="num">Clauses</th>
                </tr>
              </thead>
              <tbody>
                {inherits.rows.map((row) => (
                  <tr key={row.path.join(">") + row.license}>
                    <td className="min-w-[16rem] break-all font-mono text-xs">
                      {row.path.join(" → ")}
                    </td>
                    <td className="font-mono text-[13px]">{row.license}</td>
                    <td className="num">{row.clauses.length || "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="mt-4">
            <summary className="cursor-pointer font-mono text-xs uppercase tracking-[0.12em] text-accent">
              The query
            </summary>
            <pre className="mt-2 overflow-x-auto border border-white/10 bg-surface p-4 font-mono text-[13px] leading-relaxed">
              {inherits.cypher}
            </pre>
          </details>
        </section>
      ) : null}
      <div className="border-b border-white/15" data-testid="clause-cards">
        {cards.map((hit, index) => (
          <article
            key={hit.clause_id}
            className={`grid gap-3 border-t border-white/15 py-5 md:grid-cols-[190px_minmax(0,1fr)] md:gap-4 ${
              verdict.blocking.some((b) => b.clause_id === hit.clause_id) ? "border-t-redline" : ""
            }`}
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              §{index + 1}
              <span className="block break-all normal-case tracking-normal">{hit.clause_id}</span>
            </p>
            <div className="min-w-0 [overflow-wrap:anywhere]">
              <p className="font-serif text-xl leading-snug">{hit.summary}</p>
              {hit.quote ? (
                <blockquote className="mt-3 border-l-2 border-redline/70 pl-3 font-serif text-[15px] italic text-muted">
                  From the licence: {hit.quote}
                </blockquote>
              ) : null}
              {hit.source_url ? (
                <a
                  className="mt-2 inline-block font-mono text-xs uppercase tracking-[0.12em] text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent"
                  href={hit.source_url}
                >
                  Source{hit.section ? `, ${hit.section}` : ""}
                </a>
              ) : null}
              {hit.status ? (
                <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
                  Obligation: {hit.status}
                </p>
              ) : null}
            </div>
          </article>
        ))}
      </div>
      <HostedPanel modelId={modelId} hq={hq} />
      {verdict.verdict === "BLOCKED" ? (
        <section className="border-t border-white/15 pt-5" data-testid="alternatives">
          <h2 className="font-serif text-2xl font-light leading-tight">
            Alternatives in our candidate set
          </h2>
          {verdict.alternatives.length > 0 ? (
            <div className="ledger-wrap mt-4">
              <table className="ledger">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {verdict.alternatives.map((alt) => (
                    <tr key={alt.model_id}>
                      <td className="min-w-[12rem] break-all font-mono text-[13px]">
                        <Link
                          className="text-text decoration-white/30 hover:underline"
                          href={`/m/${alt.model_id.split("/")[0]}/${alt.model_id.split("/")[1]}?hq=${hq}`}
                        >
                          {alt.model_id}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap font-mono text-xs uppercase text-muted">
                        {alt.verdict.replaceAll("_", " ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted">
              {verdict.alternatives_message || "No compliant alternative in our candidate set."}
            </p>
          )}
        </section>
      ) : null}
      {verdict.incomplete_reasons.length > 0 ? (
        <ul className="text-sm text-muted [overflow-wrap:anywhere]">
          {verdict.incomplete_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <details className="text-sm" data-testid="how-we-decided">
        <summary className="cursor-pointer font-mono text-xs uppercase tracking-[0.12em] text-accent">
          How we decided
        </summary>
        <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
          Computed in {verdict.computed_ms ?? 0} ms
        </p>
        {verdict.cypher?.q1 ? (
          <pre className="mt-2 overflow-x-auto border border-white/10 bg-surface p-4 font-mono text-[13px] leading-relaxed">
            {verdict.cypher.q1}
          </pre>
        ) : null}
        {verdict.cypher?.q2 ? (
          <pre className="mt-2 overflow-x-auto border border-white/10 bg-surface p-4 font-mono text-[13px] leading-relaxed">
            {verdict.cypher.q2}
          </pre>
        ) : null}
      </details>
      <p className="max-w-3xl text-sm leading-relaxed [overflow-wrap:anywhere]">
        {verdict.explanation}
      </p>
      <p className="border-t border-white/10 pt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
        {verdict.disclaimer}
      </p>
    </div>
  );
}
