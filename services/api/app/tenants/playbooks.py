"""Procedural memory: Playbook nodes seeded on every tenant graph."""

from __future__ import annotations

from app.graph import db

PLAYBOOKS = {
    "REVIEW_RULING": [
        "Recompute the verdict from the hub",
        "Compare with the previous ruling",
        "Propose a verdict for the owner",
    ],
    "APPROVE_RULING": [
        "Read the proposed verdict and facts",
        "Approve or reject with a reason",
    ],
    "APPROVE_POST": [
        "Review the draft note",
        "Confirm the target repo is allowlisted",
        "Approve posting or mark ready to copy",
    ],
    "CONFIRM_EDGE": [
        "Open the inferred edge evidence",
        "Confirm or reject the parent link",
    ],
}

_SEED = """
UNWIND $rows AS row
MERGE (p:Playbook {kind: row.kind})
SET p.steps = row.steps
RETURN count(p) AS n
"""


def seed_playbooks(graph: str) -> None:
    rows = [{"kind": kind, "steps": steps} for kind, steps in PLAYBOOKS.items()]
    db.query(graph, _SEED, {"rows": rows})
