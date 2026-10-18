"use client";

import { useCallback, useEffect, useState } from "react";

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

  if (error) return <p className="mt-4 text-[#f0605a]">{error}</p>;
  if (!state) return <p className="mt-4 text-muted">Loading the shared edge…</p>;

  return (
    <section
      className="mt-6 rounded border border-white/10 bg-surface p-4"
      data-testid="compounding"
    >
      <h2 className="text-lg">Knowledge that compounds across companies</h2>
      <p className="mt-1 text-sm text-muted">
        {state.child} declares no parent. ModelBrain inferred {state.parent} from shared tokenizer
        and config fingerprints. Strict mode refuses inferred lineage, so a strict company gets
        CANNOT DETERMINE until two independent companies confirm the edge. Each company&apos;s
        confirmation stays in its own graph; the shared graph only sees a salted hash.
      </p>
      <p className="mt-3 text-sm" data-testid="edge-state">
        Edge trust tier: <span className="font-mono">{state.edge?.tier ?? "?"}</span> ·
        confirmations: <span className="font-mono">{state.edge?.confirmations ?? 0}</span> · strict
        verdict for a German company: <span className="font-mono">{verdict}</span>
      </p>
      <button
        type="button"
        className="mt-3 rounded bg-accent px-4 py-2 text-sm font-medium text-[#0f1419] disabled:opacity-50"
        onClick={confirm}
        disabled={busy}
        data-testid="confirm-edge"
      >
        {busy ? "Confirming…" : "Confirm this edge as my sandbox company"}
      </button>
      {result?.ok ? (
        <p className="mt-3 text-sm" data-testid="confirm-result">
          Tier {result.tier_before} → {result.tier_after} with {result.confirmations} independent
          confirmations.
          {result.fan_out
            ? ` The change fanned out and reopened ${result.fan_out.reopened.length} decision(s) that rested on it.`
            : " Your company had already confirmed, or the edge is already trusted."}
        </p>
      ) : null}
      {result && !result.ok ? <p className="mt-3 text-sm text-muted">{result.reason}</p> : null}
    </section>
  );
}
