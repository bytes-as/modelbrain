import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter_Tight, Newsreader } from "next/font/google";
import { SiteFooter } from "./components/site-footer";
import { SiteHeader } from "./components/site-header";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  style: ["normal", "italic"],
  weight: ["300", "400", "500"],
});
const interTight = Inter_Tight({ subsets: ["latin"], variable: "--font-inter-tight" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "ModelBrain · The licence your model actually inherited",
  description:
    "ModelBrain reads a Hugging Face model's real lineage, and its weights, in FalkorDB, and tells your team whether you can ship it, here, and who signs off.",
  openGraph: {
    title: "ModelBrain · The licence your model actually inherited",
    description:
      "Model cards can be wrong. Weights can't. Lineage, licence clauses and company memory in one graph.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // Font variables on <html>: the theme tokens on :root reference them.
    <html
      lang="en"
      className={`${newsreader.variable} ${interTight.variable} ${plexMono.variable}`}
    >
      <body className="flex min-h-screen flex-col">
        <SiteHeader />
        <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</div>
        <SiteFooter />
      </body>
    </html>
  );
}
