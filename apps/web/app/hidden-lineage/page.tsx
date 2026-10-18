"use client";

import { useEffect, useState } from "react";

import { Exhibit, ExhibitHeader, ModelRef, Part, Status } from "../components/exhibit";
import { Algorithms } from "./algorithms";
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

  const models = rows.reduce((sum, row) => sum + row.model_ids.length, 0);
  const inferred = rows.reduce((sum, row) => sum + (row.inferred_edges?.length ?? 0), 0);

  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit B · Hidden lineage"
        source="Live from FalkorDB · WCC, PageRank, betweenness, label propagation"
        title={
          <>
            Lineage the model cards <em className="italic">do not declare.</em>
          </>
        }
        lede="Inferred from shared fingerprints and from the weights, raised in trust when two independent companies agree."
        facts={
          rows.length > 0
            ? [
                { value: rows.length, label: "Fingerprint components" },
                { value: models, label: "Models in them" },
                ...(inferred > 0 ? [{ value: inferred, label: "Inferred edges" }] : []),
              ]
            : undefined
        }
      />

      <Part
        n="1"
        title="Countersignature: two companies confirm one edge"
        note="Each company's confirmation stays in its own graph; the shared graph only sees a salted hash."
      >
        <Compounding />
      </Part>

      <Part
        n="2"
        title="Graph algorithms over the whole lineage"
        note="Computed by FalkorDB inside Cypher over every model in the hub."
      >
        <Algorithms />
      </Part>

      <Part
        n="3"
        title="Models that share file fingerprints"
        note="Weakly connected components (WCC) over shared file fingerprints, with the edges inferred inside each."
      >
        {error ? <Status state="error" error={error} /> : null}
        <ol className={rows.length ? "border-b border-white/10" : undefined}>
          {rows.map((row) => (
            <li
              key={String(row.component_id)}
              className="grid gap-3 border-t border-white/10 py-5 md:grid-cols-[140px_minmax(0,1fr)] md:gap-6"
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
                Component {row.component_id}
                <span className="mt-1 block normal-case tracking-normal">
                  {row.model_ids.length} models
                </span>
              </p>
              <div className="min-w-0">
                <ul className="flex flex-wrap gap-x-5 gap-y-1.5">
                  {row.model_ids.map((id) => (
                    <li key={id} className="min-w-0">
                      <ModelRef id={id} hub={false} />
                    </li>
                  ))}
                </ul>
                {row.inferred_edges?.length ? (
                  <ul className="mt-4 space-y-1.5 border-l border-white/15 pl-4">
                    {row.inferred_edges.map((e) => (
                      <li
                        key={`${e.child}-${e.parent}`}
                        className="font-mono text-xs text-muted [overflow-wrap:anywhere]"
                      >
                        {e.child} <span className="text-text">→</span> {e.parent}{" "}
                        <span className="whitespace-nowrap uppercase tracking-[0.1em]">
                          · {e.relation} · tier {e.tier}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </Part>
    </Exhibit>
  );
}
