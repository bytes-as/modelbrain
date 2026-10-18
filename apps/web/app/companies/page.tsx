import { CompaniesView } from "./companies-view";

export default function CompaniesPage() {
  return (
    <main>
      <h1 className="text-3xl">Companies</h1>
      <p className="mt-2 max-w-2xl text-muted">
        Two fictional companies on one FalkorDB instance. Kestrel is in Germany. Harbor is in the
        United States. The hub does not store which company uses which model.
      </p>
      <CompaniesView />
    </main>
  );
}
