"use client";

import Link from "next/link";
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
} from "../../components/exhibit";

type Step = { date: string; kind: string; label: string; ref: string };
type Child = { id: string; relation: string };
type Affected = { graph: string; ruling_id: string; deployment_id: string; owner_id: string };
type DiscussionRow = {
  num: number;
  title: string;
  status: string;
  opened_at: string;
  url: string;
  outcome: string | null;
  days: number | null;
};
type Replay = {
  discussions?: DiscussionRow[];
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

  const row =
    "grid grid-cols-[96px_minmax(0,1fr)] gap-4 border-t border-white/10 py-3 md:grid-cols-[140px_minmax(0,1fr)]";
  const date = "font-mono text-[11px] uppercase tracking-[0.12em] text-muted";
  const remembered = data?.discussions?.filter((d) => d.outcome) ?? [];
  let part = 0;
  const next = () => String(++part);

  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit D · Amendment"
        source="Live from FalkorDB · Hugging Face commits and discussions"
        title={
          <>
            The licence was amended upstream. <em>No descendant was served notice.</em>
          </>
        }
        lede="A real upstream licence fix, replayed through the graph. One model fixed its licence files 130 days after someone asked. None of its children inherited the fix. ModelBrain walks the lineage in FalkorDB and reopens every company decision that rested on any of them."
        facts={
          data
            ? [
                { value: data.fix.days_after_report, label: "Days from report to fix" },
                { value: data.children.length, label: "Children on the Hub" },
                { value: data.leverage.descendants, label: "Descendants in graph" },
                { value: data.leverage.not_inherited, label: "Without the notice" },
              ]
            : undefined
        }
      />

      <div className="[overflow-wrap:anywhere]">
        {error ? (
          <div className="pt-8">
            <Status state="error" error={error} />
          </div>
        ) : null}
        {!data && !error ? (
          <div className="pt-8">
            <Status state="loading" />
          </div>
        ) : null}

        {data ? (
          <>
            <Part
              n={next()}
              title="What happened on the Hub"
              note={
                <>
                  Today the card of <ModelRef id={data.model_id} /> still declares{" "}
                  <Licence name={data.card_license_now} />; its weights come from{" "}
                  <ModelRef id={data.base_model} />.
                </>
              }
            >
              <ol className="border-b border-white/10" data-testid="replay-timeline">
                {data.timeline.map((step) => (
                  <li key={`${step.date}-${step.ref}`} className={row}>
                    <span className={date}>{step.date}</span>
                    <span className="text-[15px] leading-relaxed">
                      <span
                        className={
                          step.kind === "LICENSE_FILE_ADDED"
                            ? "font-serif text-xl italic text-accent"
                            : ""
                        }
                      >
                        {step.label}
                      </span>{" "}
                      <a
                        className="whitespace-nowrap font-mono text-[11px] uppercase tracking-[0.12em] text-muted hover:text-text"
                        href={refLink(data.model_id, step.ref)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        source ↗
                      </a>
                    </span>
                  </li>
                ))}
              </ol>
            </Part>

            {remembered.length > 0 ? (
              <Part
                n={next()}
                title="What the graph remembers"
                note={`${data.discussions?.length ?? 0} discussions on this model are stored as graph nodes linked to it.`}
                testId="discussion-memory"
              >
                <ol className="border-b border-white/10">
                  {remembered.map((d) => (
                    <li key={d.num} className={row}>
                      <span className={date}>{d.opened_at.slice(0, 10)}</span>
                      <span className="text-[15px] leading-relaxed">
                        <a
                          className="text-text underline decoration-white/30 underline-offset-4 hover:decoration-text"
                          href={d.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Discussion #{d.num} &quot;{d.title}&quot;
                        </a>
                        <span className="text-muted">
                          {" "}
                          · outcome{" "}
                          <span className="font-mono text-[13px] text-text">
                            {d.outcome}
                          </span> after {d.days} days
                        </span>
                      </span>
                    </li>
                  ))}
                </ol>
              </Part>
            ) : null}

            <Part
              n={next()}
              title="Who did not get the fix"
              note={
                <span data-testid="fix-leverage">
                  {data.children.length} children on the Hub. In our graph:{" "}
                  {data.leverage.descendants} descendants, {data.leverage.not_inherited} without the
                  upstream notice.
                </span>
              }
            >
              <div className="ledger-wrap">
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Child</th>
                      <th>Relation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.children.map((child) => (
                      <tr key={child.id}>
                        <td>
                          <a
                            className="break-all font-mono text-[13px] text-text hover:underline"
                            href={`${HUB}/${child.id}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {child.id} <span className="font-sans text-[11px] text-muted">↗</span>
                          </a>
                        </td>
                        <td>
                          <Tag>{child.relation}</Tag>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Part>

            <Part
              n={next()}
              title="Decisions that rest on this lineage"
              note="Runs only inside your private sandbox (a copy of the fictional Kestrel company). Nothing is posted anywhere."
            >
              <div className="ledger-wrap">
                <table className="ledger" data-testid="would-reopen">
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Ruling</th>
                      <th>Deployment</th>
                      <th>Owner</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.would_reopen.map((r) => (
                      <tr key={`${r.graph}-${r.ruling_id}`}>
                        <td>{r.graph.replace("tenant_", "")}</td>
                        <td className="font-mono text-[13px]">{r.ruling_id}</td>
                        <td className="font-mono text-[13px]">{r.deployment_id}</td>
                        <td>{r.owner_id}</td>
                      </tr>
                    ))}
                    {data.would_reopen.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="text-muted">
                          No company decision rests on this lineage yet.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <button
                type="button"
                className="mt-6 rounded-sm bg-paper px-4 py-2 font-medium text-ink hover:bg-white disabled:opacity-50"
                onClick={runReplay}
                disabled={busy}
                data-testid="run-replay"
              >
                {busy ? "Replaying…" : "Replay the fix in my sandbox"}
              </button>
            </Part>

            {run ? (
              <Part
                n={next()}
                title="Fan-out result"
                note={`Walked ${run.descendants} descendants and reopened ${run.reopened.length} decision${run.reopened.length === 1 ? "" : "s"} in ${run.ms} ms.`}
                testId="replay-result"
              >
                <div className="ledger-wrap">
                  <table className="ledger">
                    <thead>
                      <tr>
                        <th>Ruling reopened</th>
                        <th>Deployment</th>
                        <th>Review task</th>
                        <th>Assigned to</th>
                        <th>Affected</th>
                      </tr>
                    </thead>
                    <tbody>
                      {run.reopened.map((r) => (
                        <tr key={r.task_id}>
                          <td className="font-mono text-[13px]">{r.ruling_id}</td>
                          <td className="font-mono text-[13px]">{r.deployment_id}</td>
                          <td className="font-mono text-[13px]">{r.task_id}</td>
                          <td>{r.owner_id}</td>
                          <td className="min-w-[14rem]">
                            {r.affected_models.map((m) => (
                              <span key={m} className="block">
                                <ModelRef id={m} hub={false} />
                              </span>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Link
                  className="mt-6 inline-block font-mono text-xs uppercase tracking-[0.12em] text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent"
                  href="/companies"
                >
                  Open the company view to approve or reject →
                </Link>
              </Part>
            ) : null}
          </>
        ) : null}

        <Disclaimer />
      </div>
    </Exhibit>
  );
}
