"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Scored = { model: string; score: number };
type Family = { communityId: number; size: number; sample: string[] };

function ModelLink({ id }: { id: string }) {
  const [owner, name] = id.split("/");
  return (
    <Link className="text-accent" href={`/m/${owner}/${name}`}>
      {id}
    </Link>
  );
}

export function Algorithms() {
  const [hubs, setHubs] = useState<Scored[]>([]);
  const [choke, setChoke] = useState<Scored[]>([]);
  const [families, setFamilies] = useState<Family[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const get = (path: string) =>
      fetch(`${base}${path}`).then((r) => (r.ok ? r.json() : Promise.reject()));
    Promise.all([
      get("/api/algo/relabel-hubs"),
      get("/api/algo/chokepoints"),
      get("/api/algo/families"),
    ])
      .then(([h, c, f]) => {
        setHubs((h as Scored[]).slice(0, 8));
        setChoke((c as Scored[]).slice(0, 8));
        setFamilies((f as Family[]).slice(0, 6));
      })
      .catch(() => setError(true));
  }, []);

  if (error) return <p className="mt-6 text-sm text-muted">Graph algorithms unavailable.</p>;

  return (
    <section className="mt-8" data-testid="algorithms">
      <h2 className="text-xl">Graph algorithms over the whole lineage</h2>
      <p className="mt-1 text-sm text-muted">
        Computed by FalkorDB inside Cypher over every model in the hub.
      </p>
      <div className="mt-3 grid gap-4 md:grid-cols-3">
        <div className="rounded border border-white/10 bg-surface p-3">
          <p className="font-medium">Relabel hubs (PageRank)</p>
          <p className="text-xs text-muted">
            Permissive card, restrictive ancestor, ranked by influence over descendants.
          </p>
          <ol className="mt-2 space-y-1 text-sm">
            {hubs.map((row) => (
              <li key={row.model}>
                <ModelLink id={row.model} />
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded border border-white/10 bg-surface p-3">
          <p className="font-medium">Chokepoints (betweenness)</p>
          <p className="text-xs text-muted">A licence fix here reaches the most descendants.</p>
          <ol className="mt-2 space-y-1 text-sm">
            {choke.map((row) => (
              <li key={row.model}>
                <ModelLink id={row.model} />{" "}
                <span className="font-mono text-xs text-muted">{row.score.toFixed(0)}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded border border-white/10 bg-surface p-3">
          <p className="font-medium">Families (label propagation)</p>
          <p className="text-xs text-muted">Communities in the lineage graph.</p>
          <ul className="mt-2 space-y-2 text-sm">
            {families.map((family) => (
              <li key={family.communityId}>
                <span className="font-mono text-xs text-muted">{family.size} models</span>{" "}
                {family.sample.slice(0, 2).join(", ")}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
