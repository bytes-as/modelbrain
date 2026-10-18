"use client";

import { useEffect, useState } from "react";

import {
  Disclaimer,
  Exhibit,
  ExhibitHeader,
  ModelRef,
  Part,
  Status,
  Tag,
} from "../components/exhibit";

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

  const pct = (value: number | undefined) => `${((value || 0) * 100).toFixed(1)}%`;
  const rows = report?.rows || [];
  const shown = rows.slice(0, 40);
  const baseline = report?.baselines?.declared_licence_only;

  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit G · Evaluation"
        source="Live from the ModelBrain API"
        title={
          <>
            Graph verdicts, <em>checked against frozen labels.</em>
          </>
        }
        lede="Frozen labels vs graph verdicts, with the card-only baseline beside them."
        facts={
          report
            ? [
                { value: report.cases ?? "?", label: "Cases" },
                { value: report.false_allow ?? "?", label: "False ALLOW" },
                { value: pct(report.accuracy_default), label: "Default accuracy" },
                ...(baseline
                  ? [{ value: pct(baseline.match_rate), label: "Card-only baseline" }]
                  : []),
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
        {!report && !error ? (
          <div className="pt-8">
            <Status state="loading" />
          </div>
        ) : null}

        {report ? (
          <>
            <Part
              n="1"
              title="The labels"
              note="The label set is frozen; its hash identifies exactly which labels these numbers were scored against."
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
                labels sha256
              </p>
              <p className="mt-1 break-all font-mono text-[13px] text-text">
                {report.labels_sha256}
              </p>
              <p className="mt-6 text-[15px] leading-relaxed text-muted">
                cases {report.cases} · false ALLOW {report.false_allow} · default accuracy{" "}
                {pct(report.accuracy_default)}
                {baseline ? <> · card-only baseline match rate {pct(baseline.match_rate)}</> : null}
              </p>
            </Part>

            <Part
              n="2"
              title="Case by case"
              note={`Showing ${shown.length} of ${rows.length} rows. Red rows are where the graph verdict differs from the label.`}
            >
              <div className="ledger-wrap">
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Ctx</th>
                      <th>Mode</th>
                      <th>Expected</th>
                      <th>Actual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((row, i) => (
                      <tr
                        key={`${row.model_id}-${row.mode}-${i}`}
                        className={row.match ? "" : "text-redline"}
                      >
                        <td className="min-w-[12rem]">
                          <ModelRef id={row.model_id} hub={false} />
                        </td>
                        <td className="font-mono text-[13px]">{row.context}</td>
                        <td className="font-mono text-[13px]">{row.mode}</td>
                        <td className="font-mono text-[13px]">{row.expected}</td>
                        <td className="whitespace-nowrap font-mono text-[13px]">
                          {row.actual}
                          {row.match ? null : (
                            <span className="ml-2">
                              <Tag tone="red">mismatch</Tag>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Part>
          </>
        ) : null}

        <Disclaimer />
      </div>
    </Exhibit>
  );
}
