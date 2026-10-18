export default function HomePage() {
  return (
    <main>
      <h1 className="text-3xl text-text sm:text-4xl">Can you ship this model?</h1>
      <p className="mt-3 max-w-2xl text-muted">
        Paste any Hugging Face model id. We follow its real ancestry in FalkorDB and tell you what
        its upstream licences require for your company.
      </p>
    </main>
  );
}
