import { VerdictView } from "./verdict-view";

export default async function ModelVerdictPage({
  params,
  searchParams,
}: {
  params: Promise<{ owner: string; name: string }>;
  searchParams: Promise<{ hq?: string; c?: string }>;
}) {
  const { owner, name } = await params;
  const query = await searchParams;
  const hq = (query.hq || "DE").toUpperCase();
  const commercial = query.c !== "0";
  const modelId = `${owner}/${name}`;

  return (
    <main>
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
        §1 · Verdict for a company in {hq} · {commercial ? "commercial" : "non-commercial"} use
      </p>
      <h1
        className="mt-3 break-all font-serif font-light leading-[1.05] tracking-[-0.02em]"
        style={{ fontSize: "clamp(1.9rem, 4.4vw, 3.6rem)" }}
      >
        {modelId}
      </h1>
      <VerdictView modelId={modelId} hq={hq} commercial={commercial} />
    </main>
  );
}
