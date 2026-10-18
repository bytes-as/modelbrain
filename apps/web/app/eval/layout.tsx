import type { Metadata } from "next";

import { pageMetadata } from "../lib/seo";

export const metadata: Metadata = pageMetadata(
  "Evaluation",
  "Graph verdicts checked against a frozen, hashed label set, with a card-only baseline beside them.",
  "/eval",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
