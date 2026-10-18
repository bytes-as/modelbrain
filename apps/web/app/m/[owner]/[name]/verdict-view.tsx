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
  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const [error, setError] = useState("");
  const [verdict, setVerdict] = useState<Verdict | null>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const controller = new AbortController();
    setState("loading");
    fetch(`${base}/api/verdict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_id: modelId,
        context: { hq_country: hq, commercial, markets: [hq] },
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) {
          setError(body.error?.message || "The check failed.");
          setState("error");
          return;
        }
        setVerdict(body);
        setState("done");
      })
      .catch(() => {
        setError("The API is not reachable.");
        setState("error");
      });
    return () => controller.abort();
  }, [modelId, hq, commercial]);

  const flip = hq === "US" ? "DE" : "US";
  const [owner, name] = modelId.split("/");

  if (state === "loading") {
    return <p className="mt-6 text-muted">Following the model&apos;s ancestry in FalkorDB…</p>;
  }
  if (state === "error" || !verdict) {
    return <p className="mt-6 text-[#f0605a]">{error} Try again from the check page.</p>;
  }

  const label = verdict.verdict.replaceAll("_", " ");
  const cards = [...verdict.blocking, ...verdict.needs_counsel, ...verdict.obligations];
  const path = cards[0]?.path ?? [];

  return (
    <div className="mt-6 space-y-6">
      <p
        className="inline-block rounded px-3 py-2 text-lg font-medium"
        style={{ background: COLOUR[verdict.verdict] ?? "#9aa3ae", color: "#0f1419" }}
      >
        {label}
      </p>
      {verdict.declared_differs ? (
        <p className="text-sm text-muted">
          Card declares {verdict.declared_license} · Inherits{" "}
          {verdict.inherited_licenses.join(", ") || "no further licence"}
        </p>
      ) : null}
      <p className="text-sm">
        Context: {hq}, {commercial ? "commercial" : "non-commercial"}.{" "}
        <Link
          className="text-accent"
          href={`/m/${owner}/${name}?hq=${flip}&c=${commercial ? "1" : "0"}`}
        >
          Flip HQ to {flip}
        </Link>
      </p>
      {path.length > 0 ? (
        <ol className="flex flex-wrap gap-2 font-mono text-xs">
          {path.map((id) => (
            <li key={id} className="rounded bg-surface px-2 py-1">
              {id}
            </li>
          ))}
        </ol>
      ) : null}
      <div className="space-y-3">
        {cards.map((hit) => (
          <article key={hit.clause_id} className="rounded border border-white/10 bg-surface p-4">
            <h2 className="font-mono text-sm">{hit.clause_id}</h2>
            <p className="mt-2 text-sm">{hit.summary}</p>
            {hit.quote ? (
              <blockquote className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted">
                {hit.quote}
              </blockquote>
            ) : null}
            {hit.source_url ? (
              <a className="mt-2 inline-block text-sm text-accent" href={hit.source_url}>
                Source{hit.section ? `, ${hit.section}` : ""}
              </a>
            ) : null}
          </article>
        ))}
      </div>
      {verdict.incomplete_reasons.length > 0 ? (
        <ul className="text-sm text-muted">
          {verdict.incomplete_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <p className="text-sm">{verdict.explanation}</p>
      <p className="text-sm text-muted">{verdict.disclaimer}</p>
    </div>
  );
}
