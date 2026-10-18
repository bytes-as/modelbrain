"""Task leases and approval handoffs."""

from __future__ import annotations

import time
from typing import Any

from app.errors import ApiError
from app.graph import db
from app.graph.queries import T5
from app.graph.rows import as_rows
from app.ids import new_id
from app.tenants.playbooks import PLAYBOOKS
from app.tenants.rulings import write_ruling


def list_tasks(graph: str, state: str | None = None) -> list[dict[str, object]]:
    rows = as_rows(
        db.ro_query(
            graph,
            """
            MATCH (t:Task)
            WHERE $state IS NULL OR t.state = $state
            OPTIONAL MATCH (t)-[:ABOUT]->(r:Ruling)
            OPTIONAL MATCH (t)-[:FOLLOWS]->(p:Playbook)
            OPTIONAL MATCH (t)-[:HANDED_OFF_FROM]->(prev:Task)
            RETURN t.id AS id, t.kind AS kind, t.state AS state, t.created_by_agent AS created_by_agent,
                   t.proposed_verdict AS proposed_verdict, r.id AS ruling_id,
                   coalesce(p.steps, []) AS playbook_steps, prev.id AS handed_off_from
            ORDER BY t.created_at DESC
            """,
            {"state": state},
        )
    )
    return rows


def claim_task(graph: str, task_id: str, agent: str) -> bool:
    now = int(time.time() * 1000)
    rows = as_rows(db.query(graph, T5, {"task_id": task_id, "now": now, "agent": agent}))
    return bool(rows)


def create_review_task(graph: str, *, ruling_id: str, owner_id: str, reason: str) -> str:
    task_id = new_id("task")
    event_id = new_id("evt")
    now = int(time.time() * 1000)
    db.query(
        graph,
        """
        MATCH (r:Ruling {id: $ruling_id}), (p:Person {id: $owner_id})
        CREATE (e:Event {id: $event_id, kind: 'REOPENED', at: $now, reason: $reason})
        CREATE (e)-[:ON]->(r)
        CREATE (t:Task {id: $task_id, kind: 'REVIEW_RULING', state: 'OPEN',
                        created_by_agent: 'watcher', created_at: $now})
        CREATE (t)-[:ABOUT]->(r)
        CREATE (t)-[:ASSIGNED_TO]->(p)
        WITH t
        MATCH (pb:Playbook {kind: 'REVIEW_RULING'})
        CREATE (t)-[:FOLLOWS]->(pb)
        RETURN t.id
        """,
        {
            "ruling_id": ruling_id,
            "owner_id": owner_id,
            "event_id": event_id,
            "task_id": task_id,
            "now": now,
            "reason": reason,
        },
    )
    return task_id


def handoff_to_owner(
    graph: str,
    review_task_id: str,
    *,
    proposed_verdict: str,
    proposed_ruling: dict[str, Any],
    owner_id: str,
) -> str:
    approve_id = new_id("task")
    now = int(time.time() * 1000)
    import json

    db.query(
        graph,
        """
        MATCH (review:Task {id: $review_id}), (p:Person {id: $owner_id})
        SET review.state = 'AWAITING_APPROVAL',
            review.proposed_verdict = $proposed_verdict,
            review.proposed_ruling_json = $proposed_json
        CREATE (t:Task {id: $approve_id, kind: 'APPROVE_RULING', state: 'OPEN',
                        created_by_agent: 'auditor', created_at: $now,
                        proposed_verdict: $proposed_verdict,
                        proposed_ruling_json: $proposed_json})
        CREATE (t)-[:HANDED_OFF_FROM]->(review)
        CREATE (t)-[:ASSIGNED_TO]->(p)
        WITH t, review
        OPTIONAL MATCH (review)-[:ABOUT]->(r:Ruling)
        FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END |
          CREATE (t)-[:ABOUT]->(r)
        )
        WITH t
        MATCH (pb:Playbook {kind: 'APPROVE_RULING'})
        CREATE (t)-[:FOLLOWS]->(pb)
        RETURN t.id
        """,
        {
            "review_id": review_task_id,
            "owner_id": owner_id,
            "approve_id": approve_id,
            "now": now,
            "proposed_verdict": proposed_verdict,
            "proposed_json": json.dumps(proposed_ruling),
        },
    )
    return approve_id


def audit_deployment(graph: str, deployment_id: str, hub: str = "hub") -> dict[str, Any] | None:
    """Auditor: recompute a deployment's verdict from FalkorDB with the company's context."""
    from app.engine.verdict import verdict_from_graph
    from app.graph.queries import T9, T10

    company = as_rows(db.ro_query(graph, T9))
    deployment = next(
        (r for r in as_rows(db.ro_query(graph, T10)) if r.get("deployment_id") == deployment_id),
        None,
    )
    if not company or not deployment or not deployment.get("model"):
        return None
    hq = str(company[0].get("hq_country") or "US")
    return verdict_from_graph(
        str(deployment["model"]),
        {
            "hq_country": hq,
            "markets": [hq],
            "commercial": True,
            "mau": int(company[0].get("mau") or 0),
            "distributes_weights": False,
            "end_user_only": False,
        },
        graph=hub,
    )


def approve_task(graph: str, task_id: str, person_id: str, hub: str = "hub") -> dict[str, object]:
    import json

    rows = as_rows(
        db.ro_query(
            graph,
            """
            MATCH (t:Task {id: $task_id})
            OPTIONAL MATCH (t)-[:ABOUT]->(r:Ruling)-[:FOR]->(dep:Deployment)
            RETURN t.kind AS kind, t.proposed_ruling_json AS proposed,
                   t.proposed_verdict AS proposed_verdict, dep.id AS deployment_id,
                   r.id AS old_ruling_id
            """,
            {"task_id": task_id},
        )
    )
    if not rows:
        raise ApiError("MODEL_NOT_FOUND", f"No task '{task_id}'.")
    row = rows[0]
    now = int(time.time() * 1000)
    ruling_id = None
    verdict_now: str | None = None
    if row.get("kind") == "APPROVE_RULING" and row.get("proposed") and row.get("deployment_id"):
        proposed = json.loads(str(row["proposed"]))
        ruling_id = write_ruling(
            graph,
            deployment_id=str(row["deployment_id"]),
            verdict=proposed,
            expected_ruling_id=str(row["old_ruling_id"]) if row.get("old_ruling_id") else None,
        )
        verdict_now = str(proposed.get("verdict") or "")
    elif row.get("kind") == "REVIEW_RULING" and row.get("deployment_id"):
        # The owner approves the review: the Auditor recomputes and a new ruling
        # supersedes the old one (rulings are append-only).
        decided = audit_deployment(graph, str(row["deployment_id"]), hub)
        if decided is not None:
            ruling_id = write_ruling(
                graph,
                deployment_id=str(row["deployment_id"]),
                verdict=decided,
                expected_ruling_id=str(row["old_ruling_id"]) if row.get("old_ruling_id") else None,
            )
            verdict_now = str(decided.get("verdict") or "")
    db.query(
        graph,
        """
        MATCH (t:Task {id: $task_id}), (p:Person {id: $person_id})
        SET t.state = 'DONE'
        WITH t, p
        OPTIONAL MATCH (t)-[:ABOUT]->(r:Ruling)
        FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END |
          CREATE (e:Event {id: $event_id, kind: 'APPROVED', at: $now, reason: 'owner approved'})
          CREATE (e)-[:ON]->(r)
          CREATE (p)-[:SIGNED]->(e)
        )
        """,
        {
            "task_id": task_id,
            "person_id": person_id,
            "event_id": new_id("evt"),
            "now": now,
        },
    )
    return {"ruling_id": ruling_id, "verdict": verdict_now, "supersedes": row.get("old_ruling_id")}


def reject_task(graph: str, task_id: str, person_id: str, reason: str) -> dict[str, object]:
    now = int(time.time() * 1000)
    db.query(
        graph,
        """
        MATCH (t:Task {id: $task_id}), (p:Person {id: $person_id})
        SET t.state = 'DONE'
        WITH t, p
        OPTIONAL MATCH (t)-[:ABOUT]->(r:Ruling)
        FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END |
          CREATE (e:Event {id: $event_id, kind: 'REJECTED', at: $now, reason: $reason})
          CREATE (e)-[:ON]->(r)
          CREATE (p)-[:SIGNED]->(e)
        )
        """,
        {
            "task_id": task_id,
            "person_id": person_id,
            "event_id": new_id("evt"),
            "now": now,
            "reason": reason,
        },
    )
    return {"ok": True}


def playbook_for(kind: str) -> list[str]:
    return list(PLAYBOOKS.get(kind) or [])
