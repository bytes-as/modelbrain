import type { Metadata } from "next";

import { pageMetadata } from "../lib/seo";
import { Exhibit, ExhibitHeader } from "../components/exhibit";
import { CompaniesView } from "./companies-view";

export const metadata: Metadata = pageMetadata(
  "Companies",
  "Two fictional companies on one FalkorDB instance, each in its own private graph: deployments, rulings with their evidence, and the tasks an upstream change opens.",
  "/companies",
);

export default function CompaniesPage() {
  return (
    <Exhibit>
      <ExhibitHeader
        mark="Exhibit C · Two companies, one FalkorDB"
        source="Live from FalkorDB · tenant graphs"
        title={
          <>
            Two companies, <em className="italic">one FalkorDB.</em>
          </>
        }
        lede="Two fictional companies on one FalkorDB instance. Kestrel is in Germany. Harbor is in the United States. The hub does not store which company uses which model."
      />
      <CompaniesView />
    </Exhibit>
  );
}
