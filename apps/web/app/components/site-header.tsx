"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const NAV = [
  { href: "/", label: "Check a model" },
  { href: "/companies", label: "Companies" },
  { href: "/replay/xkev", label: "Xkev replay" },
  { href: "/live-loop", label: "Live loop" },
  { href: "/mcp", label: "MCP" },
  { href: "/eval", label: "Eval" },
  { href: "/how-it-works", label: "How it works" },
];

type Health = "loading" | "up" | "degraded" | "down";

const DOT: Record<Health, string> = {
  loading: "#9aa3ae",
  up: "#2fbf71",
  degraded: "#e9b450",
  down: "#f0605a",
};

const LABEL: Record<Health, string> = {
  loading: "Checking graph",
  up: "Graph up",
  degraded: "Degraded",
  down: "Graph down",
};

export function SiteHeader() {
  const [health, setHealth] = useState<Health>("loading");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const controller = new AbortController();
    fetch(`${base}/api/health`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          setHealth("down");
          return;
        }
        const body = (await response.json()) as { falkordb?: string; hf?: string };
        if (body.falkordb !== "up") {
          setHealth("down");
          return;
        }
        setHealth(body.hf === "ok" ? "up" : "degraded");
      })
      .catch(() => setHealth("down"));
    return () => controller.abort();
  }, []);

  return (
    <header className="border-b border-white/10 bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3">
        <Link href="/" className="text-lg text-text">
          ModelBrain
        </Link>
        <p className="ml-auto inline-flex items-center gap-2 text-xs text-muted" data-testid="health-dot">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: DOT[health] }}
            aria-hidden
          />
          <span>{LABEL[health]}</span>
        </p>
        <nav className="flex w-full flex-wrap gap-x-4 gap-y-2 text-sm text-muted">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-accent">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
      {health === "down" ? (
        <p className="bg-[#f0605a]/15 px-4 py-2 text-sm text-text" role="status">
          The graph database is restarting. Try again in a minute.
        </p>
      ) : null}
    </header>
  );
}
