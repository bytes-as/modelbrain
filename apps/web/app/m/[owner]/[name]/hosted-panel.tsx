"use client";

import { useEffect, useState } from "react";

type Provider = { slug: string; name: string; hq: string | null; datacenters: string[] | null };
type Hosted = {
  hosted: { or_id: string; name: string; providers: Provider[]; allowed: { provider: string }[] }[];
  residency?: { ok: boolean; proof: string | null };
};

const EU = new Set(
  "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split(" "),
);

export function HostedPanel({ modelId, hq }: { modelId: string; hq: string }) {
  const [data, setData] = useState<Hosted | null>(null);
  const eu = EU.has(hq.toUpperCase());

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const query = eu ? "?residency=EU" : "";
    fetch(`${base}/api/hosted/providers/${modelId}${query}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((body: Hosted | null) => setData(body))
      .catch(() => setData(null));
  }, [modelId, eu]);

  if (!data || data.hosted.length === 0) return null;
  return (
    <section className="border-t border-white/15 pt-5 text-sm" data-testid="hosted-panel">
      <h2 className="font-serif text-2xl font-light leading-tight">
        How do you run it? Through an API provider
      </h2>
      <div className="ledger-wrap mt-4">
        <table className="ledger">
          <thead>
            <tr>
              <th>Hosted as</th>
              <th>Providers</th>
            </tr>
          </thead>
          <tbody>
            {data.hosted.map((h) => (
              <tr key={h.or_id}>
                <td className="min-w-[10rem] break-all font-mono text-xs text-muted">{h.or_id}</td>
                <td className="min-w-[14rem]">
                  <span className="font-mono text-[13px]">{h.providers.length}</span> provider
                  {h.providers.length === 1 ? "" : "s"}:{" "}
                  {h.providers
                    .map(
                      (p) =>
                        `${p.name}${p.datacenters?.length ? ` (${p.datacenters.join(", ")})` : ""}`,
                    )
                    .join(" · ") || "none listed right now"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.residency ? (
        <p className="mt-4 [overflow-wrap:anywhere]" data-testid="residency">
          {data.residency.ok
            ? "At least one provider serves it from an EU datacenter."
            : `EU residency: ${data.residency.proof}.`}
        </p>
      ) : null}
      <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted">
        Through a provider the weights are not distributed to you; some clauses (such as the Llama
        3.2 multimodal EU exclusion, which exempts end users) then need counsel rather than a block.
      </p>
    </section>
  );
}
