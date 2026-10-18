import Link from "next/link";

// Inner pages are exhibits attached to the certificate on the homepage:
// a paper header that states the claim, then graphite parts with the evidence.

export function Exhibit({ children }: { children: React.ReactNode }) {
  return <main className="-mt-8 pb-8">{children}</main>;
}

export type Fact = { value: React.ReactNode; label: string };

export function ExhibitHeader({
  mark,
  source,
  title,
  lede,
  facts,
  children,
}: {
  mark: string;
  source?: string;
  title: React.ReactNode;
  lede?: React.ReactNode;
  facts?: Fact[];
  children?: React.ReactNode;
}) {
  return (
    <header className="bleed bg-paper text-ink">
      <div className="mx-auto max-w-6xl px-4 pb-10 pt-8 md:pb-14 md:pt-12">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink/20 pb-3 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-soft">
          <span>{mark}</span>
          {source ? <span>{source}</span> : null}
        </div>
        <h1
          className="mt-8 max-w-4xl font-serif font-light leading-[1.02] tracking-[-0.025em]"
          style={{ fontSize: "clamp(2.3rem, min(5.6vw, 9vh), 4.6rem)" }}
        >
          {title}
        </h1>
        {lede ? (
          <p className="mt-5 max-w-3xl font-serif text-lg italic leading-snug text-ink-soft md:text-xl">
            {lede}
          </p>
        ) : null}
        {facts && facts.length > 0 ? (
          <dl className="mt-10 grid grid-cols-2 border-t border-ink/20 md:grid-cols-4">
            {facts.map((fact) => (
              <div
                key={fact.label}
                className="border-b border-ink/10 py-4 pr-4 md:border-b-0 md:border-r md:pl-4 md:first:pl-0 md:last:border-r-0"
              >
                <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-soft">
                  {fact.label}
                </dt>
                <dd className="mt-1 font-serif text-4xl font-light tabular-nums">{fact.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {children}
      </div>
    </header>
  );
}

export function Part({
  n,
  title,
  note,
  children,
  id,
  testId,
}: {
  n: string;
  title: React.ReactNode;
  note?: React.ReactNode;
  children: React.ReactNode;
  id?: string;
  testId?: string;
}) {
  return (
    <section id={id} data-testid={testId} className="scroll-mt-24 pt-12 md:pt-16">
      <div className="grid gap-4 border-t border-white/15 pt-5 md:grid-cols-[120px_minmax(0,1fr)] md:gap-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">§{n}</p>
        <div className="min-w-0">
          <h2 className="font-serif text-3xl font-light leading-tight tracking-[-0.015em] text-text md:text-[2.4rem]">
            {title}
          </h2>
          {note ? (
            <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-muted">{note}</p>
          ) : null}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </section>
  );
}

// Loading / error / empty, said once in the same voice everywhere.
export function Status({
  state,
  error = "FalkorDB did not answer. Verdicts resume when the graph is back.",
  empty,
}: {
  state: "loading" | "error" | "empty" | "done";
  error?: string;
  empty?: string;
}) {
  if (state === "done") return null;
  const text = state === "loading" ? "Reading the graph…" : state === "error" ? error : empty;
  if (!text) return null;
  return (
    <p
      role={state === "error" ? "alert" : "status"}
      className={`font-mono text-xs uppercase tracking-[0.12em] ${
        state === "error" ? "text-redline" : "text-muted"
      }`}
    >
      {text}
    </p>
  );
}

const HUB = "https://huggingface.co";

// Model ids wrap after "/", "-", "_" or "." instead of mid-token.
export function Breakable({ text }: { text: string }) {
  const parts = text.split(/(?<=[/_.-])/);
  return (
    <>
      {parts.map((part, i) => (
        <span key={i}>
          {part}
          {i < parts.length - 1 ? <wbr /> : null}
        </span>
      ))}
    </>
  );
}

export function ModelRef({ id, hub = true }: { id: string; hub?: boolean }) {
  const [owner, name] = id.split("/");
  return (
    <span className="font-mono text-[13px] [overflow-wrap:anywhere]">
      {owner && name ? (
        <Link
          className="text-text decoration-white/30 hover:underline"
          href={`/m/${owner}/${name}`}
        >
          <Breakable text={id} />
        </Link>
      ) : (
        id
      )}
      {hub && owner && name ? (
        <a
          className="ml-1.5 whitespace-nowrap font-sans text-[11px] text-muted hover:text-text"
          href={`${HUB}/${id}`}
          target="_blank"
          rel="noreferrer"
          aria-label={`${id} on Hugging Face`}
        >
          Hub ↗
        </a>
      ) : null}
    </span>
  );
}

// A licence label. `struck` marks the card's claim that the graph contradicts.
export function Licence({ name, struck = false }: { name: string | null; struck?: boolean }) {
  if (!name) return <span className="text-muted">none</span>;
  return (
    <span
      className={`whitespace-nowrap font-mono text-[13px] ${struck ? "strike text-muted" : ""}`}
    >
      {name}
    </span>
  );
}

export function Tag({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "red";
}) {
  return (
    <span
      className={`inline-block whitespace-nowrap border px-1.5 py-px font-mono text-[10px] uppercase tracking-[0.1em] ${
        tone === "red" ? "border-redline/60 text-redline" : "border-white/20 text-muted"
      }`}
    >
      {children}
    </span>
  );
}

export function TextButton({
  children,
  onClick,
  testId,
}: {
  children: React.ReactNode;
  onClick: () => void;
  testId?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="mt-4 font-mono text-xs uppercase tracking-[0.12em] text-accent underline decoration-white/25 underline-offset-4 hover:decoration-accent"
    >
      {children}
    </button>
  );
}

export function Disclaimer() {
  return (
    <p className="mt-16 border-t border-white/10 pt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
      Automated screening, not legal advice.
    </p>
  );
}
