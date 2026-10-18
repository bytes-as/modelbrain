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

const COLOUR: Record<string, string> = {
  ALLOWED: "#2fbf71",
  ALLOWED_WITH_OBLIGATIONS: "#e9b450",
  BLOCKED: "#f0605a",
  CANNOT_DETERMINE: "#9aa3ae",
};

function Column({ overview }: { overview: Overview }) {
  const company = overview.company;
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
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export function CompaniesView() {
  const [columns, setColumns] = useState<Overview[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/api/tenants`)
      .then(async (response) => {
        if (!response.ok) throw new Error("tenants");
        const tenants = (await response.json()) as { name: string }[];
        const overviews = await Promise.all(
          tenants.map(async (tenant) => {
            const next = await fetch(`${base}/api/tenants/${tenant.name}/overview`);
            if (!next.ok) throw new Error(tenant.name);
            return (await next.json()) as Overview;
          }),
        );
        setColumns(overviews);
      })
      .catch(() => setError("Could not load the companies."));
  }, []);

  if (error) return <p className="mt-6 text-[#f0605a]">{error}</p>;
  if (columns.length === 0) return <p className="mt-6 text-muted">Loading companies…</p>;
  return (
    <div className="mt-6 grid gap-4 md:grid-cols-2">
      {columns.map((overview) => (
        <Column key={overview.company.name} overview={overview} />
      ))}
    </div>
  );
}
