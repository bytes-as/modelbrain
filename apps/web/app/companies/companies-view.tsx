"use client";

import { useEffect, useState } from "react";

import { Licence, ModelRef, Part, Status, Tag } from "../components/exhibit";

type Ruling = { id: string; verdict: string; decided_at: number | null };
type Deployment = {
  id: string;
  model_id: string;
  owner: string | null;
  latest_ruling: Ruling | null;
};
type Product = { id: string; name: string; deployments: Deployment[] };
type Overview = {
  company: { name?: string; hq_country?: string; mau?: number };
  products: Product[];
};
type Tenant = { name: string; kind?: string };
type Trace = {
  verdict?: string;
  facts?: { model_id: string; sha: string; license_key: string; clause_ids: string[] }[];
  events?: { kind: string; at: number; by: string | null }[];
};
type Task = {
  id: string;
  kind: string;
  state: string;
  playbook_steps?: string[];
};

const TEXT_BUTTON =
  "font-mono text-xs uppercase tracking-[0.12em] text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent";

function Verdict({ verdict }: { verdict: string }) {
  return <Tag tone={verdict === "BLOCKED" ? "red" : "muted"}>{verdict.replaceAll("_", " ")}</Tag>;
}

function Column({
  n,
  tenant,
  overview,
  onTrace,
}: {
  n: number;
  tenant: string;
  overview: Overview;
  onTrace: (tenant: string, rulingId: string) => void;
}) {
  const company = overview.company;
  const [tasks, setTasks] = useState<Task[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/api/tenants/${tenant}/tasks`)
      .then(async (response) => {
        if (!response.ok) return;
        setTasks((await response.json()) as Task[]);
      })
      .catch(() => undefined);
  }, [tenant]);

  return (
    <Part
      n={String(n)}
      title={company.name ?? tenant}
      note={
        <span className="font-mono text-[11px] uppercase tracking-[0.14em]">
          HQ {company.hq_country}
          {company.mau ? ` · ${company.mau.toLocaleString()} monthly active users` : ""}
        </span>
      }
    >
      <div className="space-y-10">
        {overview.products.map((product) => (
          <div key={product.id} className="min-w-0">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              {product.name}
            </h3>
            <div className="ledger-wrap mt-3">
              <table className="ledger">
                <thead>
                  <tr>
                    <th>Deployed model</th>
                    <th>Owner</th>
                    <th>Latest ruling</th>
                    <th>
                      <span className="sr-only">Trace</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {product.deployments.map((deployment) => {
                    const verdict = deployment.latest_ruling?.verdict;
                    return (
                      <tr key={deployment.id}>
                        <td className="min-w-[14rem]">
                          <ModelRef id={deployment.model_id} />
                        </td>
                        <td className="min-w-[7rem] text-muted">{deployment.owner}</td>
                        <td className="whitespace-nowrap">
                          {verdict ? (
                            <Verdict verdict={verdict} />
                          ) : (
                            <span className="text-muted">No ruling yet</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap text-right">
                          {deployment.latest_ruling?.id ? (
                            <button
                              type="button"
                              className={TEXT_BUTTON}
                              onClick={() => onTrace(tenant, deployment.latest_ruling!.id)}
                            >
                              Trace
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))}
        {tasks.length > 0 ? (
          <div data-testid="task-list">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Open tasks
            </h3>
            <ul className="mt-3 border-b border-white/10">
              {tasks.map((task) => (
                <li key={task.id} className="border-t border-white/10 py-4">
                  <p className="font-mono text-xs uppercase tracking-[0.1em] [overflow-wrap:anywhere]">
                    {task.kind} <span className="text-muted">· {task.state}</span>
                  </p>
                  {task.playbook_steps && task.playbook_steps.length > 0 ? (
                    <ol className="mt-2 max-w-3xl list-decimal space-y-1 pl-5 text-sm text-muted">
                      {task.playbook_steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Part>
  );
}

export function CompaniesView() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [columns, setColumns] = useState<Record<string, Overview>>({});
  const [error, setError] = useState("");
  const [trace, setTrace] = useState<Trace | null>(null);
  const [sandboxMsg, setSandboxMsg] = useState("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    let own: { tenant: string; token: string } | null = null;
    try {
      own = JSON.parse(sessionStorage.getItem("modelbrain_sandbox") ?? "null");
    } catch {
      own = null;
    }
    const auth: Record<string, string> = own?.token ? { "X-Tenant-Token": own.token } : {};
    fetch(`${base}/api/tenants`, { headers: auth })
      .then(async (response) => {
        if (!response.ok) throw new Error("tenants");
        const listed = (await response.json()) as Tenant[];
        // The two demo companies, plus this visitor's own sandbox when it is still alive.
        const chosen = listed.filter(
          (item) => item.kind === "fixed" || (item.kind === "sandbox" && item.name === own?.tenant),
        );
        const settled = await Promise.allSettled(
          chosen.map(async (tenant) => {
            const next = await fetch(`${base}/api/tenants/${tenant.name}/overview`, {
              headers: tenant.kind === "sandbox" ? auth : {},
            });
            if (!next.ok) throw new Error(tenant.name);
            return [tenant.name, (await next.json()) as Overview] as const;
          }),
        );
        const loaded = settled.flatMap((result) =>
          result.status === "fulfilled" ? [result.value] : [],
        );
        if (loaded.length === 0) throw new Error("overviews");
        const names = new Set(loaded.map(([name]) => name));
        setTenants(chosen.filter((tenant) => names.has(tenant.name)));
        setColumns(Object.fromEntries(loaded));
      })
      .catch(() => setError("Could not load the companies."));
  }, []);

  async function trySandbox(template: "kestrel" | "harbor") {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${base}/api/sandbox`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template }),
    });
    if (!response.ok) {
      setSandboxMsg("Could not create a sandbox.");
      return;
    }
    const body = (await response.json()) as { tenant: string; token: string };
    sessionStorage.setItem("modelbrain_sandbox", JSON.stringify(body));
    setSandboxMsg(`Sandbox ${body.tenant} ready. Token stored in sessionStorage.`);
  }

  async function onTrace(tenant: string, rulingId: string) {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${base}/api/tenants/${tenant}/rulings/${rulingId}/trace`);
    if (!response.ok) return;
    setTrace((await response.json()) as Trace);
  }

  if (error)
    return (
      <div className="pt-12">
        <Status state="error" error={error} />
      </div>
    );
  if (tenants.length === 0)
    return (
      <div className="pt-12">
        <Status state="loading" />
      </div>
    );

  const shown = tenants.filter((tenant) => columns[tenant.name]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-white/10 py-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
          Your own sandbox
        </p>
        <button
          type="button"
          className="rounded-sm bg-paper px-4 py-2 font-medium text-ink hover:bg-white"
          onClick={() => trySandbox("kestrel")}
        >
          Try it as Kestrel
        </button>
        <button type="button" className={TEXT_BUTTON} onClick={() => trySandbox("harbor")}>
          Try it as Harbor
        </button>
        {sandboxMsg ? (
          <p className="basis-full font-mono text-xs text-muted [overflow-wrap:anywhere]">
            {sandboxMsg}
          </p>
        ) : null}
      </div>
      {shown.map((tenant, index) => (
        <Column
          key={tenant.name}
          n={index + 1}
          tenant={tenant.name}
          overview={columns[tenant.name]}
          onTrace={onTrace}
        />
      ))}
      {trace ? (
        <aside
          className="fixed inset-x-0 bottom-0 z-40 max-h-[70vh] overflow-y-auto border-t border-white/20 bg-surface shadow-[0_-12px_32px_rgba(0,0,0,0.45)]"
          data-testid="trace-drawer"
          aria-label="Decision trace"
        >
          <div className="mx-auto max-w-6xl px-4 py-6">
            <div className="flex items-baseline justify-between gap-4 border-b border-white/15 pb-3">
              <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                Decision trace
              </h3>
              <button type="button" className={TEXT_BUTTON} onClick={() => setTrace(null)}>
                Close
              </button>
            </div>
            {trace.verdict ? (
              <p
                className={`mt-4 font-serif text-3xl font-light ${
                  trace.verdict === "BLOCKED" ? "text-redline" : "text-text"
                }`}
              >
                {trace.verdict.replaceAll("_", " ")}
              </p>
            ) : null}
            {(trace.facts || []).length > 0 ? (
              <div className="ledger-wrap mt-5">
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Licence</th>
                      <th>Commit</th>
                      <th>Clauses</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(trace.facts || []).map((fact) => (
                      <tr key={`${fact.model_id}-${fact.sha}`}>
                        <td className="min-w-[14rem]">
                          <ModelRef id={fact.model_id} hub={false} />
                        </td>
                        <td>
                          <Licence name={fact.license_key} />
                        </td>
                        <td className="whitespace-nowrap">
                          {fact.sha ? (
                            <a
                              className="font-mono text-[13px] text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent"
                              href={`https://huggingface.co/${fact.model_id}/commit/${fact.sha}`}
                            >
                              {fact.sha.slice(0, 7)} ↗
                            </a>
                          ) : (
                            <span className="text-muted">none</span>
                          )}
                        </td>
                        <td className="min-w-[8rem] font-mono text-xs text-muted">
                          {fact.clause_ids?.length ? fact.clause_ids.join(", ") : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {(trace.events || []).length > 0 ? (
              <ol className="mt-5 border-b border-white/10">
                {(trace.events || []).map((event, index) => (
                  <li
                    key={`${event.kind}-${index}`}
                    className="border-t border-white/10 py-2 font-mono text-xs uppercase tracking-[0.1em] text-muted"
                  >
                    {event.kind}
                    {event.by ? <span className="normal-case"> · by {event.by}</span> : null}
                  </li>
                ))}
              </ol>
            ) : null}
          </div>
        </aside>
      ) : null}
    </div>
  );
}
