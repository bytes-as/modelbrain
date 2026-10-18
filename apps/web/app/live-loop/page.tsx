"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Disclaimer, Exhibit, ExhibitHeader, ModelRef, Part, Status } from "../components/exhibit";

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

  const reopened = runs.reduce((sum, run) => sum + run.reopened, 0);
  const link = "text-ink underline decoration-ink/30 underline-offset-4 hover:decoration-redline";

  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit E · Watcher register"
        source="Live from FalkorDB"
        title={
          <>
            Every upstream change, <em>entered in the register.</em>
          </>
        }
        lede={
          <>
            Every time an upstream model changes, or two companies confirm a lineage edge,
            ModelBrain walks the lineage in FalkorDB and reopens the decisions that rested on it.
            This is the audit trail of those runs. To trigger one yourself, use the{" "}
            <Link className={link} href="/replay/xkev">
              Xkev replay
            </Link>{" "}
            or confirm an edge on{" "}
            <Link className={link} href="/hidden-lineage">
              Hidden lineage
            </Link>
            .
          </>
        }
        facts={
          state === "done" && runs.length > 0
            ? [
                { value: runs.length, label: "Latest runs" },
                { value: reopened, label: "Decisions reopened" },
              ]
            : undefined
        }
      />

      <div className="[overflow-wrap:anywhere]">
        <Part n="1" title="Fan-out runs, newest first">
          <Status
            state={state === "done" && runs.length === 0 ? "empty" : state}
            error="Could not load the log. FalkorDB may be unavailable."
            empty="No runs yet."
          />
          <ol
            className={runs.length > 0 ? "border-b border-white/10" : ""}
            data-testid="fanout-log"
          >
            {runs.map((run) => {
              const at = new Date(run.at).toISOString();
              return (
                <li
                  key={run.id}
                  className="grid grid-cols-[96px_minmax(0,1fr)] gap-4 border-t border-white/10 py-4 md:grid-cols-[140px_minmax(0,1fr)]"
                >
                  <time
                    dateTime={at}
                    className="font-mono text-[11px] uppercase leading-relaxed tracking-[0.12em] text-muted"
                  >
                    {at.slice(0, 10)}
                    <span className="block">{at.slice(11, 19)} UTC</span>
                  </time>
                  <div className="min-w-0">
                    <p className="text-[15px] leading-relaxed text-text">{run.reason}</p>
                    <p className="mt-1 text-sm leading-relaxed text-muted">
                      <ModelRef id={run.model_id} hub={false} />: {run.descendants} descendants (
                      {run.not_inherited} without the upstream notice), {run.reopened} decision
                      {run.reopened === 1 ? "" : "s"} reopened across {run.graphs.length} company
                      graph{run.graphs.length === 1 ? "" : "s"}.
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </Part>

        <Disclaimer />
      </div>
    </Exhibit>
  );
}
