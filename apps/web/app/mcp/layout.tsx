import type { Metadata } from "next";

import { pageMetadata } from "../lib/seo";

export const metadata: Metadata = pageMetadata(
  "Connect your agent",
  "Give Claude Code, Cursor or any MCP client a can_i_use tool, so the agent checks a model's inherited licence before from_pretrained.",
  "/mcp",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
