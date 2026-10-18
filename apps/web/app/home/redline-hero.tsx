"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

// Real public models, as of 18 Oct 2026 (ModelBrain's own measurements). Not accusations:
// the machine-readable metadata and the weights disagree.
const CASES = [
  {
    model: "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
    card: "apache-2.0",
    inherited: "Llama 3.2",
    note: "Quantised from Xkev/Llama-3.2V-11B-cot, fine-tuned from Meta's Llama 3.2 11B Vision. The multimodal licence grants no rights to companies based in the EU.",
    verdict: "Blocked for a company in Berlin",
  },
  {
    model: "TroyDoesAI/Llama-3.1-8B-Instruct",
    card: "wtfpl",
    inherited: "Llama 3.1",
    note: "Sampled weights identical to meta-llama/Llama-3.1-8B-Instruct (cosine 1.000). Read from 2 KB of the real weights. Llama 3.1 terms apply whatever the card says.",
    verdict: "Llama terms apply · counsel",
  },
  {
    model: "CMSManhattan/JiRackUltra_1b",
    card: "mit",
    inherited: "Apache 2.0",
    note: "Sampled weights identical to DeepSeek-R1-Distill-Qwen-1.5B, which derives from Qwen2.5-Math-1.5B. The card declares no base model.",
    verdict: "Parent hidden by the card",
  },
  {
    model: "microsoft/UserLM-8b",
    card: "Llama 3.1",
    inherited: "Llama 3",
    note: "Declares Llama 3.1 8B as its base; the weights match Llama 3 8B more closely (0.9986 against 0.9868).",
    verdict: "Declared parent contradicted",
  },
];

const EXAMPLES = [
  "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
  "TroyDoesAI/Llama-3.1-8B-Instruct",
  "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8",
  "Qwen/Qwen2.5-7B-Instruct",
];

type Suggestion = { id: string; license: string | null; differs: boolean };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function RedlineHero() {
  const router = useRouter();
  const [i, setI] = useState(0);
  const [struck, setStruck] = useState(true);
  const [paused, setPaused] = useState(false);
  const [modelId, setModelId] = useState("");
  const [hq, setHq] = useState("DE");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const c = CASES[i];

  // Autocomplete from the models already in the graph (they answer instantly).
  useEffect(() => {
    const term = modelId.trim();
    if (term.length < 2) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`${API}/api/models/search?q=${encodeURIComponent(term)}&limit=8`, {
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : []))
        .then((rows: Suggestion[]) => {
          setSuggestions(rows);
          setActive(-1);
        })
        .catch(() => undefined);
    }, 150);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [modelId]);

  function choose(id: string) {
    setModelId(id);
    setOpen(false);
    check(id);
  }

  useEffect(() => {
    if (paused) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const swap = window.setTimeout(() => setStruck(false), 5200);
    const next = window.setTimeout(() => {
      setI((v) => (v + 1) % CASES.length);
      setStruck(true);
    }, 5800);
    return () => {
      window.clearTimeout(swap);
      window.clearTimeout(next);
    };
  }, [i, paused]);

  function check(id: string) {
    const [owner, name] = id.trim().split("/");
    if (!owner || !name) return;
    router.push(`/m/${owner}/${name}?hq=${hq}&c=1`);
  }

  return (
    <section
      id="check"
      className="bleed scroll-mt-24 bg-paper text-ink"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="mx-auto max-w-6xl px-4 pb-14 pt-10 md:pb-16 md:pt-14">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink/20 pb-3 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-soft">
          <span>Certificate of inheritance · ModelBrain</span>
          <span>
            Exhibit {i + 1} of {CASES.length} · real public model · as of 18 Oct 2026
          </span>
        </div>

        <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_300px]">
          <h1
            className="font-serif font-light leading-[0.98] tracking-[-0.025em]"
            style={{ fontSize: "clamp(2.6rem, min(7vw, 10vh), 6.2rem)" }}
            aria-live="polite"
          >
            The card says{" "}
            <span className="strike" style={{ ["--strike" as string]: struck ? 1 : 0 }}>
              {c.card}
            </span>
            .
            <br />
            The weights say{" "}
            <em
              className="text-redline"
              style={{ opacity: struck ? 1 : 0, transition: "opacity 400ms" }}
            >
              {c.inherited}
            </em>
            .
          </h1>
          <aside
            className="relative self-end border-l-2 border-redline pl-4 text-sm"
            style={{ opacity: struck ? 1 : 0, transition: "opacity 400ms" }}
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-redline">
              Redline
            </p>
            <p className="mt-1 break-all font-mono text-xs text-ink">{c.model}</p>
            <p className="mt-2 font-serif text-[15px] italic leading-snug text-ink-soft">
              {c.note}
            </p>
            <p className="stamp mt-4 font-mono text-[11px] text-redline">{c.verdict}</p>
          </aside>
        </div>

        <div className="mt-8 max-w-4xl border-t border-ink/20 pt-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-soft">
            §1 · Your terms
          </p>
          <div className="mt-3 font-serif text-2xl leading-relaxed md:text-[1.9rem]">
            <span>A company headquartered in </span>
            <select
              aria-label="Headquarters country"
              value={hq}
              onChange={(e) => setHq(e.target.value)}
              className="mx-1 border-b-2 border-ink bg-transparent font-mono text-xl focus:outline-none"
            >
              {["DE", "FR", "NL", "IE", "US", "GB", "IN", "JP"].map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <span> may ship </span>
            <span className="relative mx-1 inline-block w-full align-baseline md:w-[30rem]">
              <input
                aria-label="Hugging Face model id"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={open && suggestions.length > 0}
                aria-controls="model-suggestions"
                aria-activedescendant={active >= 0 ? `model-option-${active}` : undefined}
                autoComplete="off"
                spellCheck={false}
                value={modelId}
                onChange={(e) => {
                  setModelId(e.target.value);
                  setOpen(true);
                }}
                onFocus={() => {
                  setPaused(true);
                  setOpen(true);
                }}
                onBlur={() => window.setTimeout(() => setOpen(false), 120)}
                onKeyDown={(e) => {
                  const shown = open ? suggestions : [];
                  if (e.key === "ArrowDown" && shown.length) {
                    e.preventDefault();
                    setActive((v) => (v + 1) % shown.length);
                  } else if (e.key === "ArrowUp" && shown.length) {
                    e.preventDefault();
                    setActive((v) => (v <= 0 ? shown.length - 1 : v - 1));
                  } else if (e.key === "Escape") {
                    setOpen(false);
                  } else if (e.key === "Enter") {
                    if (active >= 0 && shown[active]) choose(shown[active].id);
                    else check(modelId || c.model);
                  }
                }}
                placeholder={c.model}
                className="w-full min-w-0 border-b-2 border-ink bg-transparent font-mono text-lg placeholder:text-ink/35 focus:outline-none md:text-xl"
              />
              {open && suggestions.length > 0 ? (
                <ul
                  id="model-suggestions"
                  role="listbox"
                  aria-label="Models in the graph"
                  className="absolute left-0 right-0 top-full z-30 mt-1 max-h-80 overflow-auto border border-ink/20 bg-paper py-1 font-sans text-base shadow-xl shadow-ink/10"
                >
                  {suggestions.map((row, n) => (
                    <li
                      key={row.id}
                      id={`model-option-${n}`}
                      role="option"
                      aria-selected={n === active}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        choose(row.id);
                      }}
                      onMouseEnter={() => setActive(n)}
                      className={`flex cursor-pointer items-baseline justify-between gap-3 px-3 py-2 ${
                        n === active ? "bg-paper-2" : ""
                      }`}
                    >
                      <span className="min-w-0 font-mono text-[13px] text-ink [overflow-wrap:anywhere]">
                        {row.id}
                      </span>
                      <span className="flex shrink-0 items-baseline gap-2 font-mono text-[11px] text-ink-soft">
                        {row.license ?? "no licence"}
                        {row.differs ? (
                          <span className="border border-redline/60 px-1 uppercase tracking-[0.08em] text-redline">
                            card disagrees
                          </span>
                        ) : null}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </span>
            <span> commercially, if the graph says so.</span>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => check(modelId || c.model)}
              className="rounded-sm bg-ink px-5 py-3 font-medium text-paper transition-colors hover:bg-redline"
            >
              Check the terms →
            </button>
            <span className="font-mono text-xs text-ink-soft">or try</span>
            {EXAMPLES.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => check(id)}
                className="font-mono text-xs text-ink-soft underline decoration-ink/30 hover:text-redline"
              >
                {id}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
