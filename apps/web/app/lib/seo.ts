import type { Metadata } from "next";

// Next replaces (does not merge) openGraph/twitter per page, so each page gets the full set.
const IMAGE = {
  width: 1200,
  height: 630,
  alt: "The card says apache-2.0. The weights say Llama 3.2. ModelBrain",
};

export function pageMetadata(title: string, description: string, path: string): Metadata {
  const full = `${title} · ModelBrain`;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: "website",
      siteName: "ModelBrain",
      locale: "en_GB",
      url: path,
      title: full,
      description,
      images: [{ url: "/opengraph-image", ...IMAGE }],
    },
    twitter: {
      card: "summary_large_image",
      title: full,
      description,
      images: [{ url: "/twitter-image", ...IMAGE }],
    },
  };
}
