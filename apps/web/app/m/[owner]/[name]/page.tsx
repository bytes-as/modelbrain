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
      <p className="font-mono text-sm text-muted">{modelId}</p>
      <h1 className="mt-2 text-3xl">Can you ship this model?</h1>
      <VerdictView modelId={modelId} hq={hq} commercial={commercial} />
    </main>
  );
}
