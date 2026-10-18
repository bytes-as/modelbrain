"""G078: conversation turns persist on a tenant graph."""

from __future__ import annotations

from uuid import uuid4

from app.graph import db
from app.graph.schema import apply_schema
from app.tenants.conversations import list_conversations, record_turn


def test_record_and_list_turns() -> None:
    db.connect(tries=5, delay_s=0.5)
    graph = f"g078_{uuid4().hex[:8]}"
    try:
        apply_schema()
        record_turn(
            graph,
            channel="mcp",
            tool="can_i_use",
            args={"model_id": "Qwen/Qwen2.5-7B-Instruct"},
            verdict="ALLOWED",
        )
        found = list_conversations(graph)
        assert found
        assert found[0]["turns"]
        assert found[0]["turns"][0]["tool"] == "can_i_use"
    finally:
        try:
            db.delete_graph(graph)
        except Exception:
            pass
