"use client";

import { useEffect, useState } from "react";

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

const COLOUR: Record<string, string> = {
  ALLOWED: "#2fbf71",
  ALLOWED_WITH_OBLIGATIONS: "#e9b450",
  BLOCKED: "#f0605a",
  CANNOT_DETERMINE: "#9aa3ae",
};

function Column({
  tenant,
  overview,
  onTrace,
}: {
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
    <section className="rounded border border-white/10 bg-surface p-4">
      <h2 className="text-xl">{company.name}</h2>
      <p className="mt-1 text-sm text-muted">
        HQ {company.hq_country}
        {company.mau ? ` · ${company.mau.toLocaleString()} monthly active users` : ""}
      </p>
      <div className="mt-4 space-y-4">
        {overview.products.map((product) => (
          <div key={product.id}>
            <h3 className="text-sm text-muted">{product.name}</h3>
            <ul className="mt-2 space-y-2">
              {product.deployments.map((deployment) => {
                const verdict = deployment.latest_ruling?.verdict;
                return (
                  <li key={deployment.id} className="rounded border border-white/10 p-3">
                    <p className="font-mono text-xs">{deployment.model_id}</p>
                    <p className="mt-1 text-sm text-muted">{deployment.owner}</p>
                    {verdict ? (
                      <p
                        className="mt-2 inline-block rounded px-2 py-1 text-xs font-medium"
                        style={{ background: COLOUR[verdict] ?? "#9aa3ae", color: "#0f1419" }}
                      >
                        {verdict.replaceAll("_", " ")}
                      </p>
                    ) : (
                      <p className="mt-2 text-sm text-muted">No ruling yet</p>
                    )}
                    {deployment.latest_ruling?.id ? (
                      <button
                        type="button"
                        className="mt-2 text-xs text-accent"
                        onClick={() => onTrace(tenant, deployment.latest_ruling!.id)}
                      >
                        Trace
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
      {tasks.length > 0 ? (
        <div className="mt-4" data-testid="task-list">
          <h3 className="text-sm text-muted">Open tasks</h3>
          <ul className="mt-2 space-y-2">
            {tasks.map((task) => (
              <li key={task.id} className="rounded border border-white/10 p-3 text-sm">
                <p className="font-mono text-xs">
                  {task.kind} · {task.state}
                </p>
                {task.playbook_steps && task.playbook_steps.length > 0 ? (
                  <ol className="mt-2 list-decimal pl-4 text-xs text-muted">
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
    </section>
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
    fetch(`${base}/api/tenants`)
      .then(async (response) => {
        if (!response.ok) throw new Error("tenants");
        const listed = (await response.json()) as Tenant[];
        const fixed = listed.filter((item) => item.kind !== "sandbox" || item.name.startsWith("sbx_"));
        // Prefer fixed tenants for the two-column demo; include caller's sandbox if present.
        const chosen = listed.filter((item) => item.kind === "fixed" || item.kind === "sandbox");
        setTenants(chosen.length ? chosen : fixed);
        const overviews = await Promise.all(
          (chosen.length ? chosen : fixed).map(async (tenant) => {
            const next = await fetch(`${base}/api/tenants/${tenant.name}/overview`);
            if (!next.ok) throw new Error(tenant.name);
            return [tenant.name, (await next.json()) as Overview] as const;
          }),
        );
        setColumns(Object.fromEntries(overviews));
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

  if (error) return <p className="mt-6 text-[#f0605a]">{error}</p>;
  if (tenants.length === 0) return <p className="mt-6 text-muted">Loading companies…</p>;

  return (
    <div className="mt-6 space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border border-white/10 px-3 py-2 text-sm text-accent"
          onClick={() => trySandbox("kestrel")}
        >
          Try it as Kestrel
        </button>
        <button
          type="button"
          className="rounded border border-white/10 px-3 py-2 text-sm text-accent"
          onClick={() => trySandbox("harbor")}
        >
          Try it as Harbor
        </button>
        {sandboxMsg ? <p className="text-sm text-muted">{sandboxMsg}</p> : null}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {tenants.map((tenant) =>
          columns[tenant.name] ? (
            <Column
              key={tenant.name}
              tenant={tenant.name}
              overview={columns[tenant.name]}
              onTrace={onTrace}
            />
          ) : null,
        )}
      </div>
      {trace ? (
        <aside className="rounded border border-white/10 bg-surface p-4" data-testid="trace-drawer">
          <h3 className="text-lg">Decision trace</h3>
          <p className="mt-1 text-sm">{trace.verdict}</p>
          <ul className="mt-3 space-y-2 text-sm">
            {(trace.facts || []).map((fact) => (
              <li key={`${fact.model_id}-${fact.sha}`}>
                {fact.model_id} · {fact.license_key}
                {fact.sha ? (
                  <>
                    {" "}
                    ·{" "}
                    <a
                      className="text-accent"
                      href={`https://huggingface.co/${fact.model_id}/commit/${fact.sha}`}
                    >
                      commit
                    </a>
                  </>
                ) : null}
                {fact.clause_ids?.length ? (
                  <span className="text-muted"> · {fact.clause_ids.join(", ")}</span>
                ) : null}
              </li>
            ))}
          </ul>
          <ul className="mt-3 text-xs text-muted">
            {(trace.events || []).map((event, index) => (
              <li key={`${event.kind}-${index}`}>
                {event.kind} {event.by ? `by ${event.by}` : ""}
              </li>
            ))}
          </ul>
          <button type="button" className="mt-3 text-sm text-accent" onClick={() => setTrace(null)}>
            Close
          </button>
        </aside>
      ) : null}
    </div>
  );
}
