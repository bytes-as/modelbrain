"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
  paths?: { path: string[]; tiers: number[]; relations: string[] }[];
};

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
      <p className="mt-6 text-muted" data-testid="verdict-loading">
        Following the model&apos;s ancestry in FalkorDB…
      </p>
    );
  }
  if (state === "queued") {
    return (
      <div className="mt-6 space-y-2" data-testid="verdict-queued">
        <p className="text-muted">Ingesting ancestry…</p>
        <ul className="font-mono text-xs text-muted">
          {progress.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
    );
  }
  if (state === "error" || !verdict) {
    return (
      <p className="mt-6 text-[#f0605a]" data-testid="verdict-error">
        {error} Try again from the check page.
      </p>
    );
  }

  const label = verdict.verdict.replaceAll("_", " ");
  const cards = [...verdict.blocking, ...verdict.needs_counsel, ...verdict.obligations];
  const path = cards[0]?.path ?? verdict.paths?.[0]?.path ?? [];

  return (
    <div className="mt-6 space-y-6" data-testid="verdict-done">
      <p
        className="inline-block rounded px-3 py-2 text-lg font-medium"
        data-testid="verdict-badge"
        style={{ background: COLOUR[verdict.verdict] ?? "#9aa3ae", color: "#0f1419" }}
      >
        {label}
      </p>
      {verdict.declared_differs ? (
        <p className="text-sm text-muted" data-testid="declared-differs">
          Card declares {verdict.declared_license} · Inherits{" "}
          {verdict.inherited_licenses.join(", ") || "no further licence"}
        </p>
      ) : null}
      <p className="text-sm" data-testid="context-chips">
        Context: {hq}, {commercial ? "commercial" : "non-commercial"}.{" "}
        <Link
          className="text-accent"
          data-testid="flip-hq"
          href={`/m/${owner}/${name}?hq=${flip}&c=${commercial ? "1" : "0"}`}
        >
          Flip HQ to {flip}
        </Link>
      </p>
      {path.length > 0 ? (
        <ol className="flex flex-wrap gap-2 font-mono text-xs" data-testid="lineage-path">
          {path.map((id) => (
            <li key={id} className="rounded bg-surface px-2 py-1">
              {id}
            </li>
          ))}
        </ol>
      ) : null}
      <div className="space-y-3" data-testid="clause-cards">
        {cards.map((hit) => (
          <article key={hit.clause_id} className="rounded border border-white/10 bg-surface p-4">
            <h2 className="font-mono text-sm">{hit.clause_id}</h2>
            <p className="mt-2 text-sm">{hit.summary}</p>
            {hit.quote ? (
              <blockquote className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted">
                From the licence: {hit.quote}
              </blockquote>
            ) : null}
            {hit.source_url ? (
              <a className="mt-2 inline-block text-sm text-accent" href={hit.source_url}>
                Source{hit.section ? `, ${hit.section}` : ""}
              </a>
            ) : null}
            {hit.status ? (
              <p className="mt-2 text-xs text-muted">Obligation: {hit.status}</p>
            ) : null}
          </article>
        ))}
      </div>
      {verdict.verdict === "BLOCKED" ? (
        <section data-testid="alternatives">
          <h2 className="text-lg">Alternatives in our candidate set</h2>
          {verdict.alternatives.length > 0 ? (
            <ul className="mt-2 space-y-1 text-sm">
              {verdict.alternatives.map((alt) => (
                <li key={alt.model_id}>
                  <Link
                    className="text-accent"
                    href={`/m/${alt.model_id.split("/")[0]}/${alt.model_id.split("/")[1]}?hq=${hq}`}
                  >
                    {alt.model_id}
                  </Link>{" "}
                  <span className="text-muted">{alt.verdict.replaceAll("_", " ")}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">
              {verdict.alternatives_message ||
                "No compliant alternative in our candidate set."}
            </p>
          )}
        </section>
      ) : null}
      {verdict.incomplete_reasons.length > 0 ? (
        <ul className="text-sm text-muted">
          {verdict.incomplete_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <details className="text-sm" data-testid="how-we-decided">
        <summary className="cursor-pointer text-accent">How we decided</summary>
        <p className="mt-2 text-muted">Computed in {verdict.computed_ms ?? 0} ms.</p>
        {verdict.cypher?.q1 ? (
          <pre className="mt-2 overflow-x-auto rounded bg-surface p-3 text-xs">{verdict.cypher.q1}</pre>
        ) : null}
        {verdict.cypher?.q2 ? (
          <pre className="mt-2 overflow-x-auto rounded bg-surface p-3 text-xs">{verdict.cypher.q2}</pre>
        ) : null}
      </details>
      <p className="text-sm">{verdict.explanation}</p>
      <p className="text-sm text-muted">{verdict.disclaimer}</p>
    </div>
  );
}
