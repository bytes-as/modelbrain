import type { Metadata } from "next";

import { pageMetadata } from "../../lib/seo";

export const metadata: Metadata = pageMetadata(
  "The Xkev amendment",
  "A real upstream licence fix replayed through the graph: fixed 130 days after it was reported, and none of its children inherited it.",
  "/replay/xkev",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
