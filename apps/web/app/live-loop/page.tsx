"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Run = {
  id: string;
  model_id: string;
  reason: string;
  at: number;
  descendants: number;
  not_inherited: number;
  reopened: number;
  graphs: string[];
};

export default function LiveLoopPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [state, setState] = useState<"loading" | "done" | "error">("loading");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/api/fanouts?limit=30`)
      .then(async (r) => {
        if (!r.ok) throw new Error();
        setRuns((await r.json()) as Run[]);
        setState("done");
      })
      .catch(() => setState("error"));
  }, []);

  return (
    <main className="[overflow-wrap:anywhere]">
      <h1 className="text-3xl">Watcher log</h1>
      <p className="mt-2 max-w-3xl text-muted">
        Every time an upstream model changes, or two companies confirm a lineage edge, ModelBrain
        walks the lineage in FalkorDB and reopens the decisions that rested on it. This is the audit
        trail of those runs. To trigger one yourself, use the{" "}
        <Link className="text-accent" href="/replay/xkev">
          Xkev replay
        </Link>{" "}
        or confirm an edge on{" "}
        <Link className="text-accent" href="/hidden-lineage">
          Hidden lineage
        </Link>
        .
      </p>
      {state === "loading" ? <p className="mt-6 text-muted">Loading…</p> : null}
      {state === "error" ? (
        <p className="mt-6 text-[#f0605a]">Could not load the log. FalkorDB may be unavailable.</p>
      ) : null}
      {state === "done" && runs.length === 0 ? (
        <p className="mt-6 text-muted">No runs yet.</p>
      ) : null}
      <ul className="mt-6 space-y-3" data-testid="fanout-log">
        {runs.map((run) => (
          <li key={run.id} className="rounded border border-white/10 bg-surface p-3 text-sm">
            <p className="font-mono text-xs text-muted">{new Date(run.at).toISOString()}</p>
            <p className="mt-1">{run.reason}</p>
            <p className="mt-1 text-muted">
              {run.model_id}: {run.descendants} descendants ({run.not_inherited} without the
              upstream notice), {run.reopened} decision{run.reopened === 1 ? "" : "s"} reopened
              across {run.graphs.length} company graph{run.graphs.length === 1 ? "" : "s"}.
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
