"""G067: expected_ruling_id returns 409 STALE_RULING for the second writer."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.errors import ApiError
from app.graph import db
from app.graph.schema import apply_schema
from app.tenants.rulings import latest_ruling_id, write_ruling


def test_stale_ruling_on_concurrent_write() -> None:
    db.connect(tries=5, delay_s=0.5)
    graph = f"g067_{uuid4().hex[:8]}"
    try:
        apply_schema()
        db.query(
            graph,
            """
            CREATE (dep:Deployment {id:'dep1', model_id:'Qwen/Qwen2.5-7B-Instruct', env:'prod'})
            """,
        )
        base = {
            "model_id": "Qwen/Qwen2.5-7B-Instruct",
            "verdict": "ALLOWED",
            "strict": False,
            "explanation": "first",
            "declared_license": "apache-2.0",
            "blocking": [],
            "obligations": [],
            "needs_counsel": [],
        }
        first = write_ruling(graph, deployment_id="dep1", verdict=base, expected_ruling_id=None)
        assert latest_ruling_id(graph, "dep1") == first
        second = write_ruling(
            graph,
            deployment_id="dep1",
            verdict={**base, "explanation": "second"},
            expected_ruling_id=first,
        )
        assert second != first
        with pytest.raises(ApiError) as raised:
            write_ruling(
                graph,
                deployment_id="dep1",
                verdict={**base, "explanation": "stale"},
                expected_ruling_id=first,
            )
        assert raised.value.code == "STALE_RULING"
    finally:
        try:
            db.delete_graph(graph)
        except Exception:
            pass
