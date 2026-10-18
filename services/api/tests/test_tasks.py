"""G066 and G068: task leases and handoff."""

from __future__ import annotations

from uuid import uuid4

from app.graph import db
from app.graph.schema import apply_schema
from app.tenants.playbooks import seed_playbooks
from app.tenants.tasks import claim_task, create_review_task, handoff_to_owner, list_tasks


def test_claim_and_handoff() -> None:
    db.connect(tries=5, delay_s=0.5)
    graph = f"g066_{uuid4().hex[:8]}"
    try:
        apply_schema()
        db.query(
            graph,
            """
            CREATE (c:Company {slug:'t', name:'Test (fictional)', hq_country:'DE', eu:true, mau:1})
            CREATE (p:Person {id:'person_owner', name:'Owner (fictional)', role:'owner'})
            CREATE (prod:Product {id:'prod', name:'Prod', commercial:true})
            CREATE (dep:Deployment {id:'dep1', model_id:'Qwen/Qwen2.5-7B-Instruct', env:'prod'})
            CREATE (prod)-[:RUNS]->(dep)
            CREATE (p)-[:OWNS]->(dep)
            CREATE (r:Ruling {id:'rul_old', verdict:'ALLOWED', strict:false, created_at:1, explanation:'x', hub_sha_set:[]})
            CREATE (r)-[:FOR]->(dep)
            """,
        )
        seed_playbooks(graph)
        task_id = create_review_task(
            graph, ruling_id="rul_old", owner_id="person_owner", reason="test reopen"
        )
        assert claim_task(graph, task_id, "auditor")
        approve_id = handoff_to_owner(
            graph,
            task_id,
            proposed_verdict="ALLOWED_WITH_OBLIGATIONS",
            proposed_ruling={
                "model_id": "Qwen/Qwen2.5-7B-Instruct",
                "verdict": "ALLOWED_WITH_OBLIGATIONS",
                "strict": False,
                "explanation": "proposed",
                "declared_license": "apache-2.0",
                "blocking": [],
                "obligations": [],
                "needs_counsel": [],
            },
            owner_id="person_owner",
        )
        tasks = list_tasks(graph)
        kinds = {t["kind"] for t in tasks}
        assert "REVIEW_RULING" in kinds
        assert "APPROVE_RULING" in kinds
        assert any(t.get("handed_off_from") == task_id for t in tasks if t["id"] == approve_id)
        assert any(t.get("playbook_steps") for t in tasks)
    finally:
        try:
            db.delete_graph(graph)
        except Exception:
            pass
