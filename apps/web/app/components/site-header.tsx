"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const PRIMARY = [
  { href: "/findings", label: "Weight DNA" },
  { href: "/hidden-lineage", label: "Lineage" },
  { href: "/companies", label: "Companies" },
  { href: "/mcp", label: "Agents" },
  { href: "/how-it-works", label: "How it works" },
];

const MORE = [
  { href: "/replay/xkev", label: "The Xkev amendment", note: "Upstream change, 9 children" },
  { href: "/live-loop", label: "Watcher", note: "Changes detected on the Hub" },
  { href: "/eval", label: "Evaluation", note: "Labelled set, false allows" },
];

type Health = "loading" | "up" | "degraded" | "down";

const STATUS: Record<Health, { label: string; colour: string; title: string }> = {
  loading: { label: "Checking", colour: "#a7a196", title: "Checking the graph" },
  up: { label: "In force", colour: "#4fb37a", title: "FalkorDB and the Hugging Face Hub answer" },
  degraded: {
    label: "Hub degraded",
    colour: "#e0a43a",
    title: "FalkorDB answers; the Hugging Face Hub is slow or down",
  },
  down: { label: "Suspended", colour: "#d6332f", title: "FalkorDB is not answering" },
};

function isActive(pathname: string | null, href: string) {
  return !!pathname && (pathname === href || pathname.startsWith(`${href}/`));
}

export function SiteHeader() {
  const [health, setHealth] = useState<Health>("loading");
  const [moreOpen, setMoreOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();
  const moreRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    setMoreOpen(false);
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!moreOpen) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key === "Escape") setMoreOpen(false);
        return;
      }
      if (!moreRef.current?.contains(event.target as Node)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [moreOpen]);

  const status = STATUS[health];
  const moreActive = MORE.some((item) => isActive(pathname, item.href));

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-bg/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-4">
        <Link
          href="/"
          aria-label="ModelBrain home"
          className="flex items-center font-serif text-[1.65rem] leading-none text-text"
        >
          {/* Newsreader sits high in its line box; nudge the caps onto the bar's centre line. */}
          <span className="inline-block translate-y-[2px]">ModelBrain</span>
        </Link>

        <nav aria-label="Main" className="hidden h-full items-center gap-7 text-[14px] lg:flex">
          {PRIMARY.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative flex h-full items-center transition-colors ${
                  active ? "text-text" : "text-muted hover:text-text"
                }`}
              >
                {item.label}
                {active ? (
                  <span className="absolute inset-x-0 bottom-0 h-[2px] bg-redline" aria-hidden />
                ) : null}
              </Link>
            );
          })}
          <div ref={moreRef} className="relative flex h-full items-center">
            <button
              type="button"
              aria-expanded={moreOpen}
              aria-haspopup="true"
              onClick={() => setMoreOpen((v) => !v)}
              className={`relative flex h-full items-center gap-1 transition-colors ${
                moreActive || moreOpen ? "text-text" : "text-muted hover:text-text"
              }`}
            >
              Exhibits
              <span
                className={`text-[10px] transition-transform ${moreOpen ? "rotate-180" : ""}`}
                aria-hidden
              >
                ▾
              </span>
              {moreActive ? (
                <span className="absolute inset-x-0 bottom-0 h-[2px] bg-redline" aria-hidden />
              ) : null}
            </button>
            {moreOpen ? (
              <div className="absolute left-1/2 top-full w-72 -translate-x-1/2 border border-white/10 bg-surface p-2 shadow-2xl shadow-black/40">
                {MORE.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="block px-3 py-2.5 hover:bg-white/5"
                    aria-current={isActive(pathname, item.href) ? "page" : undefined}
                  >
                    <span className="block text-[14px] text-text">{item.label}</span>
                    <span className="block font-mono text-[11px] text-muted">{item.note}</span>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </nav>

        <div className="ml-auto flex items-center gap-5">
          <p
            className="hidden items-center gap-2 font-mono text-[11px] uppercase tracking-[0.12em] text-muted sm:inline-flex"
            data-testid="health-dot"
            title={status.title}
          >
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ background: status.colour, boxShadow: `0 0 0 3px ${status.colour}22` }}
              aria-hidden
            />
            <span>{status.label}</span>
          </p>
          <Link
            href="/#check"
            className="hidden rounded-sm bg-paper px-4 py-2 text-[14px] font-medium text-ink transition-colors hover:bg-white md:inline-block"
          >
            Check a model
          </Link>
          <button
            type="button"
            className="text-[14px] text-text lg:hidden"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
        </div>
      </div>

      {menuOpen ? (
        <nav
          id="mobile-nav"
          aria-label="Main"
          className="border-t border-white/10 bg-bg px-4 pb-6 pt-2 lg:hidden"
        >
          {[...PRIMARY, ...MORE].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
              className={`flex items-center justify-between border-b border-white/10 py-3 text-base ${
                isActive(pathname, item.href) ? "text-text" : "text-muted"
              }`}
            >
              {item.label}
              <span aria-hidden>→</span>
            </Link>
          ))}
          <Link
            href="/#check"
            className="mt-5 block rounded-sm bg-paper px-4 py-3 text-center font-medium text-ink"
          >
            Check a model
          </Link>
        </nav>
      ) : null}

      {health === "down" ? (
        <p className="bg-redline/20 px-4 py-2 text-sm text-text" role="status">
          The graph is not answering. Verdicts resume when FalkorDB is back.
        </p>
      ) : null}
    </header>
  );
}
