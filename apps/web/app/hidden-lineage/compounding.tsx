"use client";

import { useCallback, useEffect, useState } from "react";

import { ModelRef, Status } from "../components/exhibit";

type Edge = { tier: number; confirmations: number; source: string; relation: string } | null;
type State = { child: string; parent: string; edge: Edge };
type Confirm = {
  ok: boolean;
  tier_before?: number;
  tier_after?: number;
  confirmations?: number;
  reason?: string;
  fan_out?: { descendants: number; reopened: unknown[] };
};

const base = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function strictVerdict(modelId: string): Promise<string> {
  const response = await fetch(`${base()}/api/verdict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_id: modelId,
      strict: true,
      context: { hq_country: "DE", markets: ["DE"], commercial: true },
    }),
  });
  if (!response.ok) return "unavailable";
  const body = (await response.json()) as { verdict?: string };
  return (body.verdict ?? "unavailable").replaceAll("_", " ");
}

async function sandbox(): Promise<{ tenant: string; token: string } | null> {
  try {
    const saved = sessionStorage.getItem("modelbrain_sandbox");
    if (saved) return JSON.parse(saved) as { tenant: string; token: string };
  } catch {
    /* sessionStorage unavailable */
  }
  const response = await fetch(`${base()}/api/sandbox`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template: "kestrel" }),
  });
  if (!response.ok) return null;
  const body = (await response.json()) as { tenant: string; token: string };
  try {
    sessionStorage.setItem("modelbrain_sandbox", JSON.stringify(body));
  } catch {
    /* ignore */
  }
  return body;
}

export function Compounding() {
  const [state, setState] = useState<State | null>(null);
  const [verdict, setVerdict] = useState("");
  const [result, setResult] = useState<Confirm | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const response = await fetch(`${base()}/api/demo/compounding`);
    if (!response.ok) {
      setError("Could not load the shared edge.");
      return;
    }
    const body = (await response.json()) as State;
    setState(body);
    setVerdict(await strictVerdict(body.child));
  }, []);

  useEffect(() => {
    load().catch(() => setError("Could not load the shared edge."));
  }, [load]);

  async function confirm() {
    if (!state) return;
    setBusy(true);
    setError("");
    let box = await sandbox();
    const post = (b: { tenant: string; token: string }) =>
      fetch(`${base()}/api/tenants/${b.tenant}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Tenant-Token": b.token },
        body: JSON.stringify({ child: state.child, parent: state.parent, person_id: "kes_lena" }),
      });
    let response = box ? await post(box) : null;
    if (response && response.status === 401) {
      sessionStorage.removeItem("modelbrain_sandbox");
      box = await sandbox();
      response = box ? await post(box) : null;
    }
    if (!response || !response.ok) {
      setError("Could not record the confirmation.");
    } else {
      setResult((await response.json()) as Confirm);
      await load();
    }
    setBusy(false);
  }

  if (error) return <Status state="error" error={error} />;
  if (!state) return <Status state="loading" />;

  return (
    <div data-testid="compounding">
      <p className="max-w-3xl text-[15px] leading-relaxed text-text">
        <ModelRef id={state.child} hub={false} /> declares no parent. ModelBrain inferred{" "}
        <ModelRef id={state.parent} hub={false} /> from shared tokenizer and config fingerprints.
        Strict mode refuses inferred lineage, so a strict company gets CANNOT DETERMINE until two
        independent companies confirm the edge.
      </p>

      <dl className="mt-8 grid border-t border-white/15 sm:grid-cols-3" data-testid="edge-state">
        <div className="border-b border-white/10 py-4 sm:border-b-0 sm:border-r sm:pr-4">
          <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Edge trust tier
          </dt>
          <dd className="mt-1 font-serif text-4xl font-light tabular-nums">
            {state.edge?.tier ?? "?"}
          </dd>
        </div>
        <div className="border-b border-white/10 py-4 sm:border-b-0 sm:border-r sm:px-4">
          <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Confirmations
          </dt>
          <dd className="mt-1 font-serif text-4xl font-light tabular-nums">
            {state.edge?.confirmations ?? 0}
          </dd>
        </div>
        <div className="py-4 sm:pl-4">
          <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Strict verdict · German company
          </dt>
          <dd className="mt-2 font-mono text-sm uppercase tracking-[0.08em]">{verdict}</dd>
        </div>
      </dl>

      <div className="mt-6 border-t border-white/10 pt-6">
        <button
          type="button"
          className="rounded-sm bg-paper px-4 py-2 font-medium text-ink hover:bg-white disabled:opacity-50"
          onClick={confirm}
          disabled={busy}
          data-testid="confirm-edge"
        >
          {busy ? "Confirming…" : "Confirm this edge as my sandbox company"}
        </button>
        {result?.ok ? (
          <p className="mt-4 max-w-3xl text-[15px] leading-relaxed" data-testid="confirm-result">
            <span className="font-mono">
              Tier {result.tier_before} → {result.tier_after}
            </span>{" "}
            with {result.confirmations} independent confirmations.
            {result.fan_out
              ? ` The change fanned out and reopened ${result.fan_out.reopened.length} decision(s) that rested on it.`
              : " Your company had already confirmed, or the edge is already trusted."}
          </p>
        ) : null}
        {result && !result.ok ? (
          <p className="mt-4 text-[15px] text-muted">{result.reason}</p>
        ) : null}
      </div>
    </div>
  );
}
