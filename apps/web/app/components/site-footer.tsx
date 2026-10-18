import Link from "next/link";

// The footer is the signature block of the document.
export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-white/10 bg-bg text-sm text-muted">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <p className="font-serif text-2xl text-text">Executed in FalkorDB.</p>
          <div className="mt-6 max-w-sm border-b border-white/30 pb-1 font-serif text-lg italic text-text">
            the graph
          </div>
          <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em]">
            Signature · every verdict is a Cypher query
          </p>
        </div>
        <div className="space-y-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-text">Schedule</p>
          <Link className="block hover:text-text" href="/findings">
            Weight DNA findings
          </Link>
          <Link className="block hover:text-text" href="/replay/xkev">
            The Xkev amendment
          </Link>
          <Link className="block hover:text-text" href="/mcp">
            Connect your agent (MCP)
          </Link>
          <Link className="block hover:text-text" href="/how-it-works">
            The governing engine
          </Link>
        </div>
        <div className="space-y-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-text">Boilerplate</p>
          <p>Automated screening, not legal advice.</p>
          <p>
            Data: Hugging Face Hub public metadata, sampled weights and official licence texts.
            Companies shown are fictional.
          </p>
          <a className="block hover:text-text" href="https://github.com/bytes-as/modelbrain">
            Source on GitHub
          </a>
          <p>Built for Graph Hacks · WeMakeDevs × FalkorDB.</p>
        </div>
      </div>
    </footer>
  );
}
