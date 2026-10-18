"use client";

import { useEffect, useState } from "react";

import { Compounding } from "./compounding";

type Component = {
  component_id: string | number;
  model_ids: string[];
  inferred_edges: { child: string; parent: string; relation: string; tier: number }[];
};

export default function HiddenLineagePage() {
  const [rows, setRows] = useState<Component[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/api/algo/hidden-lineage`)
      .then(async (r) => {
        if (!r.ok) throw new Error("hidden");
        setRows((await r.json()) as Component[]);
      })
      .catch(() => setError("Could not load hidden lineage."));
  }, []);

  return (
    <main>
      <h1 className="text-3xl">Hidden lineage</h1>
      <p className="mt-2 max-w-2xl text-muted">
        Models that share file fingerprints. Inferred parents are dashed edges in the graph; Confirm
        raises trust when two organisations agree.
      </p>
      <Compounding />
      {error ? <p className="mt-4 text-[#f0605a]">{error}</p> : null}
      <ul className="mt-6 space-y-4">
        {rows.map((row) => (
          <li
            key={String(row.component_id)}
            className="rounded border border-white/10 bg-surface p-4"
          >
            <p className="font-mono text-xs text-muted">component {row.component_id}</p>
            <p className="mt-2 text-sm">{row.model_ids.join(" · ")}</p>
            {row.inferred_edges?.length ? (
              <ul className="mt-2 text-xs text-muted">
                {row.inferred_edges.map((e) => (
                  <li key={`${e.child}-${e.parent}`}>
                    {e.child} → {e.parent} ({e.relation}, tier {e.tier})
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </main>
  );
}
