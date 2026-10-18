import type { Metadata } from "next";

import { pageMetadata } from "../lib/seo";

export const metadata: Metadata = pageMetadata(
  "Watcher register",
  "Every upstream change ModelBrain detected on the Hugging Face Hub, and the company decisions it reopened.",
  "/live-loop",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
