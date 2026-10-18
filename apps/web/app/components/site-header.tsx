"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

// The site is a licence document; the nav is its table of clauses.
const NAV = [
  { href: "/", n: "1", label: "Check" },
  { href: "/findings", n: "2", label: "Weight DNA" },
  { href: "/hidden-lineage", n: "3", label: "Lineage" },
  { href: "/replay/xkev", n: "4", label: "Amendments" },
  { href: "/companies", n: "5", label: "Companies" },
  { href: "/live-loop", n: "6", label: "Watcher" },
  { href: "/mcp", n: "7", label: "Agents" },
  { href: "/eval", n: "8", label: "Evidence" },
  { href: "/how-it-works", n: "9", label: "Engine" },
];

type Health = "loading" | "up" | "degraded" | "down";

const STATUS: Record<Health, { label: string; colour: string }> = {
  loading: { label: "Checking", colour: "#a7a196" },
  up: { label: "In force", colour: "#4fb37a" },
  degraded: { label: "Hub degraded", colour: "#e0a43a" },
  down: { label: "Suspended", colour: "#d6332f" },
};

export function SiteHeader() {
  const [health, setHealth] = useState<Health>("loading");
  const pathname = usePathname();

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

  const status = STATUS[health];

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-bg/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="flex items-baseline gap-3 text-text">
          <span className="font-serif text-2xl leading-none">ModelBrain</span>
          <span className="hidden font-mono text-[11px] uppercase tracking-[0.14em] text-muted md:inline">
            Terms your weights carry
          </span>
        </Link>
        <p
          className="ml-auto inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.12em] text-muted"
          data-testid="health-dot"
          title="Status of the FalkorDB graph and the Hugging Face Hub"
        >
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: status.colour }}
            aria-hidden
          />
          <span>{status.label}</span>
        </p>
        <nav
          className="-mx-1 flex w-full gap-x-1 overflow-x-auto pb-1 text-sm [scrollbar-width:none]"
          aria-label="Clauses"
        >
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/" || pathname?.startsWith("/m/")
                : pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded px-2 py-1 transition-colors ${
                  active ? "bg-accent text-ink" : "text-muted hover:text-text"
                }`}
              >
                <span className="mr-1 font-mono text-[11px] opacity-70">§{item.n}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      {health === "down" ? (
        <p className="bg-redline/20 px-4 py-2 text-sm text-text" role="status">
          The graph is not answering. Verdicts resume when FalkorDB is back.
        </p>
      ) : null}
    </header>
  );
}
