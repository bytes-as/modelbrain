import { ImageResponse } from "next/og";

export const alt = "The card says apache-2.0. The weights say Llama 3.2. ModelBrain";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PAPER = "#f3efe6";
const INK = "#16161a";
const INK_SOFT = "#57534c";
const REDLINE = "#d6332f";

// Newsreader from Google Fonts, subset to the glyphs on the card. If the fetch fails at
// build time the image still renders in the default face.
async function newsreader(weight: 300 | 400, italic: boolean, text: string) {
  try {
    const family = `Newsreader:ital,wght@${italic ? 1 : 0},${weight}`;
    const css = await fetch(
      `https://fonts.googleapis.com/css2?family=${family}&text=${encodeURIComponent(text)}`,
      { signal: AbortSignal.timeout(8000) },
    ).then((r) => r.text());
    const url = css.match(/src: url\((.+?)\) format\('(?:opentype|truetype)'\)/)?.[1];
    if (!url) return null;
    return await fetch(url, { signal: AbortSignal.timeout(8000) }).then((r) => r.arrayBuffer());
  } catch {
    return null;
  }
}

export default async function OpenGraphImage() {
  const glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,·-";
  const [light, italic] = await Promise.all([
    newsreader(300, false, glyphs),
    newsreader(300, true, glyphs),
  ]);
  const fonts = [
    ...(light
      ? [{ name: "Newsreader", data: light, weight: 300 as const, style: "normal" as const }]
      : []),
    ...(italic
      ? [{ name: "Newsreader", data: italic, weight: 300 as const, style: "italic" as const }]
      : []),
  ];

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: PAPER,
        color: INK,
        padding: "64px 80px",
        fontFamily: "Newsreader",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          borderBottom: `2px solid ${INK}22`,
          paddingBottom: 18,
          fontSize: 22,
          letterSpacing: 4,
          color: INK_SOFT,
          textTransform: "uppercase",
        }}
      >
        <span>Certificate of inheritance</span>
        <span>Real public model</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", fontSize: 88, lineHeight: 1.08 }}>
        <div style={{ display: "flex", whiteSpace: "pre" }}>
          <span>The card says </span>
          <span style={{ display: "flex", position: "relative" }}>
            <span>apache-2.0</span>
            <span
              style={{
                position: "absolute",
                left: -4,
                right: -4,
                top: 52,
                height: 7,
                background: REDLINE,
              }}
            />
          </span>
          <span>.</span>
        </div>
        <div style={{ display: "flex", whiteSpace: "pre" }}>
          <span>The weights say </span>
          <span style={{ color: REDLINE, fontStyle: "italic" }}>Llama 3.2.</span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <span style={{ fontSize: 52 }}>ModelBrain</span>
        <span
          style={{
            fontSize: 22,
            letterSpacing: 3,
            color: INK_SOFT,
            textTransform: "uppercase",
          }}
        >
          Lineage · weights · licence clauses · in FalkorDB
        </span>
      </div>
    </div>,
    { ...size, fonts },
  );
}
