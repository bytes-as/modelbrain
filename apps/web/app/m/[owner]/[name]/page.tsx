import type { Metadata } from "next";

import { pageMetadata } from "../../../lib/seo";

import { Breakable, Exhibit, ExhibitHeader } from "../../../components/exhibit";

import { VerdictView } from "./verdict-view";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ owner: string; name: string }>;
}): Promise<Metadata> {
  const { owner, name } = await params;
  const id = `${owner}/${name}`;
  return pageMetadata(
    `Can you ship ${id}?`,
    `The licence ${id} actually inherited: its lineage to the root model, the clauses that bind it, and a verdict for your company's country, read from FalkorDB.`,
    `/m/${owner}/${name}`,
  );
}

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
    <Exhibit>
      <ExhibitHeader
        mark={`§1 · Verdict for a company in ${hq} · ${commercial ? "commercial" : "non-commercial"} use`}
        source="Read from FalkorDB"
        title={
          <span className="block text-[0.78em] [overflow-wrap:anywhere]">
            <span className="text-ink-soft">{owner}/</span>
            <Breakable text={name} />
          </span>
        }
      />
      <VerdictView modelId={modelId} hq={hq} commercial={commercial} />
    </Exhibit>
  );
}
