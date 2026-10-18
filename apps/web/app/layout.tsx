import type { Metadata, Viewport } from "next";
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

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.RAILWAY_PUBLIC_DOMAIN
    ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`
    : "http://localhost:3001");

const TITLE = "ModelBrain · The licence your model actually inherited";
const DESCRIPTION =
  "Model cards can be wrong; weights can't. ModelBrain reads a Hugging Face model's real lineage and its weights in FalkorDB, carries the licence clauses down the graph, and tells your team whether you can ship it, where, and who signs off.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: TITLE, template: "%s · ModelBrain" },
  description: DESCRIPTION,
  applicationName: "ModelBrain",
  keywords: [
    "model licence",
    "AI supply chain",
    "Hugging Face",
    "model lineage",
    "weight fingerprint",
    "FalkorDB",
    "MCP",
    "licence compliance",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "ModelBrain",
    url: "/",
    locale: "en_GB",
    title: TITLE,
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#121416",
  colorScheme: "dark light",
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
