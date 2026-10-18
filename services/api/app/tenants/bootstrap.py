"""Load the fictional demo companies and give each deployment a ruling."""

from __future__ import annotations

import time
from pathlib import Path

from app.engine.verdict import verdict_from_graph
from app.graph import db
from app.graph.queries import T1, T6, T9, T10
from app.graph.rows import as_rows
from app.ids import new_id
from app.paths import repo_root

TENANTS = ("tenant_kestrel", "tenant_harbor")


def _script(path: Path) -> str:
    lines = [line for line in path.read_text().splitlines() if not line.strip().startswith("//")]
    script = "\n".join(lines).strip()
    if script.endswith(";"):
        script = script[:-1].strip()
    return script


def _company_exists(graph: str) -> bool:
    try:
        rows = as_rows(db.ro_query(graph, T9))
    except Exception:
        return False
    return bool(rows)


def ensure_tenants() -> None:
    root = repo_root() / "data" / "demo_tenants"
    for graph, filename in (
        ("tenant_kestrel", "kestrel.cypher"),
        ("tenant_harbor", "harbor.cypher"),
    ):
        if _company_exists(graph):
            continue
        try:
            db.delete_graph(graph)
        except Exception:
            pass
        db.query(graph, _script(root / filename))
    from app.graph.schema import apply_schema
    from app.tenants.playbooks import seed_playbooks

    apply_schema()
    for graph in TENANTS:
        seed_playbooks(graph)
    _seed_rulings()


def _seed_rulings() -> None:
    now = int(time.time() * 1000)
    for graph in TENANTS:
        company = as_rows(db.ro_query(graph, T9))
        if not company:
            continue
        hq = company[0].get("hq_country") or "US"
        mau = int(company[0].get("mau") or 0)
        commercial_markets = ["US"] if hq == "US" else ["DE"]
        existing = {row.get("model"): row for row in as_rows(db.ro_query(graph, T6))}
        for deployment in as_rows(db.ro_query(graph, T10)):
            model_id = deployment.get("model")
            if not model_id or model_id in existing:
                continue
            decided = verdict_from_graph(
                str(model_id),
                {
                    "hq_country": hq,
                    "markets": commercial_markets,
                    "commercial": True,
                    "mau": mau,
                    "distributes_weights": False,
                    "end_user_only": False,
                },
            )
            clause_ids = [
                hit["clause_id"]
                for hit in (decided["blocking"] + decided["obligations"] + decided["needs_counsel"])
            ]
            db.query(
                graph,
                T1,
                {
                    "deployment_id": deployment["deployment_id"],
                    "ruling_id": new_id("rul"),
                    "verdict": decided["verdict"],
                    "strict": False,
                    "now": now,
                    "explanation": decided["explanation"],
                    "hub_sha_set": [],
                    "facts": [
                        {
                            "id": new_id("fact"),
                            "model_id": model_id,
                            "sha": "",
                            "license_key": decided.get("declared_license") or "",
                            "clause_ids": clause_ids,
                            "edge_tiers": [],
                        }
                    ],
                },
            )


def list_tenants() -> list[dict[str, object]]:
    found = []
    for graph in TENANTS:
        rows = as_rows(db.ro_query(graph, T9))
        if not rows:
            continue
        row = rows[0]
        found.append(
            {
                "name": graph,
                "company": row.get("name"),
                "hq_country": row.get("hq_country"),
                "kind": "fixed",
            }
        )
    return found


def overview(graph: str) -> dict[str, object]:
    company_rows = as_rows(db.ro_query(graph, T9))
    company = company_rows[0] if company_rows else {}
    rulings = {row.get("model"): row for row in as_rows(db.ro_query(graph, T6))}
    products: dict[str, dict[str, object]] = {}
    for row in as_rows(db.ro_query(graph, T10)):
        product_id = str(row.get("product_id"))
        product = products.setdefault(
            product_id,
            {"id": product_id, "name": row.get("product"), "deployments": []},
        )
        ruling = rulings.get(row.get("model"))
        deployments = product["deployments"]
        assert isinstance(deployments, list)
        deployments.append(
            {
                "id": row.get("deployment_id"),
                "model_id": row.get("model"),
                "owner": row.get("owner"),
                "latest_ruling": (
                    None
                    if not ruling
                    else {
                        "id": ruling.get("ruling_id"),
                        "verdict": ruling.get("verdict"),
                        "decided_at": ruling.get("decided_at"),
                    }
                ),
            }
        )
    return {"company": company, "products": list(products.values())}
