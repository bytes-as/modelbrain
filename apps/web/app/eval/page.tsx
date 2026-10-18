"use client";

import { useEffect, useState } from "react";

type Report = {
  labels_sha256?: string;
  false_allow?: number;
  accuracy_default?: number;
  cases?: number;
  baselines?: { declared_licence_only?: { match_rate?: number } };
  rows?: {
    model_id: string;
    context: string;
    mode: string;
    expected: string;
    actual: string;
    match: boolean;
  }[];
};

export default function EvalPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/api/eval`)
      .then(async (r) => {
        if (!r.ok) throw new Error("eval");
        setReport((await r.json()) as Report);
      })
      .catch(() => setError("Could not reach the API. Check that it is running and try again."));
  }, []);

  return (
    <main className="[overflow-wrap:anywhere]">
      <h1 className="text-3xl">Eval</h1>
      <p className="mt-2 text-muted">
        Frozen labels vs graph verdicts. Automated screening, not legal advice.
      </p>
      {error ? <p className="mt-4 text-muted">{error}</p> : null}
      {report ? (
        <div className="mt-6 space-y-4">
          <p className="font-mono text-xs">labels sha256: {report.labels_sha256}</p>
          <p className="text-sm">
            cases {report.cases} · false ALLOW {report.false_allow} · default accuracy{" "}
            {((report.accuracy_default || 0) * 100).toFixed(1)}%
          </p>
          {report.baselines?.declared_licence_only ? (
            <p className="text-sm text-muted">
              Card-only baseline match rate{" "}
              {((report.baselines.declared_licence_only.match_rate || 0) * 100).toFixed(1)}%
            </p>
          ) : null}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-muted">
                  <th className="py-1">model</th>
                  <th>ctx</th>
                  <th>mode</th>
                  <th>expected</th>
                  <th>actual</th>
                </tr>
              </thead>
              <tbody>
                {(report.rows || []).slice(0, 40).map((row, i) => (
                  <tr
                    key={`${row.model_id}-${row.mode}-${i}`}
                    className={row.match ? "" : "text-[#f0605a]"}
                  >
                    <td className="font-mono py-1">{row.model_id}</td>
                    <td>{row.context}</td>
                    <td>{row.mode}</td>
                    <td>{row.expected}</td>
                    <td>{row.actual}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </main>
  );
}
