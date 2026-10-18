"use client";

import { useEffect, useState } from "react";

import { ModelRef, Status } from "../components/exhibit";

type Scored = { model: string; score: number };
type Family = { communityId: number; size: number; sample: string[] };

function Block({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <h3 className="font-serif text-xl font-light text-text">{title}</h3>
      <p className="mt-1 text-sm text-muted">{note}</p>
      <div className="ledger-wrap mt-4">{children}</div>
    </div>
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

  if (error) return <Status state="error" error="Graph algorithms unavailable." />;

  return (
    <div className="space-y-12" data-testid="algorithms">
      <div className="grid gap-12 lg:grid-cols-2 lg:gap-10">
        <Block
          title="Relabel hubs · PageRank"
          note="Permissive card, restrictive ancestor, ranked by influence over descendants."
        >
          <table className="ledger">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Model</th>
              </tr>
            </thead>
            <tbody>
              {hubs.map((row, index) => (
                <tr key={row.model}>
                  <td className="num w-8 text-muted">{index + 1}</td>
                  <td className="min-w-[14rem]">
                    <ModelRef id={row.model} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Block>
        <Block
          title="Chokepoints · betweenness"
          note="A licence fix here reaches the most descendants."
        >
          <table className="ledger">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Model</th>
                <th className="num">Betweenness</th>
              </tr>
            </thead>
            <tbody>
              {choke.map((row, index) => (
                <tr key={row.model}>
                  <td className="num w-8 text-muted">{index + 1}</td>
                  <td className="min-w-[14rem]">
                    <ModelRef id={row.model} />
                  </td>
                  <td className="num">{row.score.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Block>
      </div>
      <Block title="Families · label propagation" note="Communities in the lineage graph.">
        <table className="ledger">
          <thead>
            <tr>
              <th className="num">Community</th>
              <th className="num">Models</th>
              <th>Sample</th>
            </tr>
          </thead>
          <tbody>
            {families.map((family) => (
              <tr key={family.communityId}>
                <td className="num text-muted">{family.communityId}</td>
                <td className="num">{family.size}</td>
                <td className="min-w-[16rem]">
                  <span className="flex flex-col gap-1">
                    {family.sample.slice(0, 2).map((id) => (
                      <ModelRef key={id} id={id} hub={false} />
                    ))}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Block>
    </div>
  );
}
