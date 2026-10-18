"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Step = { date: string; kind: string; label: string; ref: string };
type Child = { id: string; relation: string };
type Affected = { graph: string; ruling_id: string; deployment_id: string; owner_id: string };
type Replay = {
  model_id: string;
  base_model: string;
  card_license_now: string;
  timeline: Step[];
  fix: { date: string; commit: string; days_after_report: number; change: string };
  children: Child[];
  graph_descendants: string[];
  leverage: { descendants: number; not_inherited: number };
  would_reopen: Affected[];
};
type Reopened = Affected & { task_id: string; affected_models: string[] };
type FanOut = { descendants: number; reopened: Reopened[]; ms: number; reason: string };

const HUB = "https://huggingface.co";

function refLink(model: string, ref: string) {
  if (ref.startsWith("http")) return ref;
  return `${HUB}/${model}/commit/${ref}`;
}

export default function XkevReplayPage() {
  const [data, setData] = useState<Replay | null>(null);
  const [error, setError] = useState("");
  const [run, setRun] = useState<FanOut | null>(null);
  const [busy, setBusy] = useState(false);
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    fetch(`${base}/api/replay/xkev`)
      .then(async (r) => {
        if (!r.ok) throw new Error();
        setData((await r.json()) as Replay);
      })
      .catch(() => setError("Could not load the replay. FalkorDB may be unavailable."));
  }, [base]);

  async function sandbox(): Promise<{ tenant: string; token: string } | null> {
    try {
      const saved = sessionStorage.getItem("modelbrain_sandbox");
      if (saved) return JSON.parse(saved) as { tenant: string; token: string };
    } catch {
      /* sessionStorage unavailable */
    }
    const response = await fetch(`${base}/api/sandbox`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template: "kestrel" }),
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { tenant: string; token: string };
    try {
      sessionStorage.setItem("modelbrain_sandbox", JSON.stringify(body));
    } catch {
      /* ignore */
    }
    return body;
  }

  async function runReplay() {
    setBusy(true);
    setError("");
    const box = await sandbox();
    if (!box) {
      setError("Could not create a sandbox.");
      setBusy(false);
      return;
    }
    let response = await fetch(`${base}/api/replay/xkev/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Tenant-Token": box.token },
      body: JSON.stringify({ tenant: box.tenant }),
    });
    if (response.status === 401) {
      // Saved sandbox expired: start a fresh one once.
      sessionStorage.removeItem("modelbrain_sandbox");
      const fresh = await sandbox();
      if (fresh) {
        response = await fetch(`${base}/api/replay/xkev/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Tenant-Token": fresh.token },
          body: JSON.stringify({ tenant: fresh.tenant }),
        });
      }
    }
    if (!response.ok) {
      setError("The replay could not run.");
    } else {
      setRun((await response.json()) as FanOut);
    }
    setBusy(false);
  }

  return (
    <main className="[overflow-wrap:anywhere]">
      <h1 className="text-3xl">Xkev replay</h1>
      <p className="mt-2 max-w-3xl text-muted">
        A real upstream licence fix, replayed through the graph. One model fixed its licence files
        130 days after someone asked. None of its children inherited the fix. ModelBrain walks the
        lineage in FalkorDB and reopens every company decision that rested on any of them.
      </p>
      {error ? <p className="mt-4 text-[#f0605a]">{error}</p> : null}
      {!data && !error ? <p className="mt-6 text-muted">Loading…</p> : null}
      {data ? (
        <>
          <section className="mt-8">
            <h2 className="text-xl">What happened on the Hub</h2>
            <ol
              className="mt-3 space-y-2 border-l border-white/10 pl-4 text-sm"
              data-testid="replay-timeline"
            >
              {data.timeline.map((step) => (
                <li key={`${step.date}-${step.ref}`}>
                  <span className="font-mono text-xs text-muted">{step.date}</span>{" "}
                  <span className={step.kind === "LICENSE_FILE_ADDED" ? "text-accent" : ""}>
                    {step.label}
                  </span>{" "}
                  <a
                    className="text-xs text-muted"
                    href={refLink(data.model_id, step.ref)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    source ↗
                  </a>
                </li>
              ))}
            </ol>
            <p className="mt-3 text-sm text-muted">
              Today the card of {data.model_id} still declares {data.card_license_now}; its weights
              come from {data.base_model}.
            </p>
          </section>

          <section className="mt-8">
            <h2 className="text-xl">Who did not get the fix</h2>
            <p className="mt-2 text-sm text-muted" data-testid="fix-leverage">
              {data.children.length} children on the Hub. In our graph: {data.leverage.descendants}{" "}
              descendants, {data.leverage.not_inherited} without the upstream notice.
            </p>
            <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
              {data.children.map((child) => (
                <li key={child.id}>
                  <a
                    className="text-accent"
                    href={`${HUB}/${child.id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {child.id}
                  </a>{" "}
                  <span className="text-xs text-muted">{child.relation}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-8">
            <h2 className="text-xl">Decisions that rest on this lineage</h2>
            <ul className="mt-2 space-y-1 text-sm" data-testid="would-reopen">
              {data.would_reopen.map((row) => (
                <li key={`${row.graph}-${row.ruling_id}`}>
                  {row.graph.replace("tenant_", "")}: ruling {row.ruling_id} for {row.deployment_id}{" "}
                  (owner {row.owner_id})
                </li>
              ))}
              {data.would_reopen.length === 0 ? (
                <li className="text-muted">No company decision rests on this lineage yet.</li>
              ) : null}
            </ul>
            <button
              type="button"
              className="mt-4 rounded bg-accent px-4 py-2 text-sm font-medium text-[#0f1419] disabled:opacity-50"
              onClick={runReplay}
              disabled={busy}
              data-testid="run-replay"
            >
              {busy ? "Replaying…" : "Replay the fix in my sandbox"}
            </button>
            <p className="mt-2 text-xs text-muted">
              Runs only inside your private sandbox (a copy of the fictional Kestrel company).
              Nothing is posted anywhere.
            </p>
          </section>

          {run ? (
            <section
              className="mt-8 rounded border border-white/10 bg-surface p-4"
              data-testid="replay-result"
            >
              <h2 className="text-lg">Fan-out result</h2>
              <p className="mt-1 text-sm text-muted">
                Walked {run.descendants} descendants and reopened {run.reopened.length} decision
                {run.reopened.length === 1 ? "" : "s"} in {run.ms} ms.
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {run.reopened.map((row) => (
                  <li key={row.task_id}>
                    Ruling {row.ruling_id} ({row.deployment_id}) reopened; review task {row.task_id}{" "}
                    assigned to {row.owner_id}. Affected: {row.affected_models.join(", ")}
                  </li>
                ))}
              </ul>
              <Link className="mt-3 inline-block text-sm text-accent" href="/companies">
                Open the company view to approve or reject →
              </Link>
            </section>
          ) : null}
        </>
      ) : null}
      <p className="mt-10 text-sm text-muted">Automated screening, not legal advice.</p>
    </main>
  );
}
