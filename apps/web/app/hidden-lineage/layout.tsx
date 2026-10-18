import type { Metadata } from "next";

import { pageMetadata } from "../lib/seo";

export const metadata: Metadata = pageMetadata(
  "Hidden lineage",
  "Lineage the model cards do not declare, from shared fingerprints and weights, with PageRank, betweenness and community detection run inside FalkorDB.",
  "/hidden-lineage",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
