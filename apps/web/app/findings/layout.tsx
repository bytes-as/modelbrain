import type { Metadata } from "next";

import { pageMetadata } from "../lib/seo";

export const metadata: Metadata = pageMetadata(
  "Weight DNA findings",
  "Models whose sampled weights match a parent their card does not declare, and cards whose declared parent the weights contradict. Live from FalkorDB's vector index.",
  "/findings",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
