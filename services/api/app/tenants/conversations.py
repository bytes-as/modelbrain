"""Persistent conversation history on tenant graphs."""

from __future__ import annotations

import json
import time

from app.graph import db
from app.graph.rows import as_rows
from app.ids import new_id


def record_turn(
    graph: str,
    *,
    channel: str,
    tool: str,
    args: dict,
    verdict: str | None = None,
    ruling_id: str | None = None,
) -> str:
    now = int(time.time() * 1000)
    conversation_id = "conv_" + channel
    turn_id = new_id("turn")
    db.query(
        graph,
        """
        MERGE (c:Conversation {id: $conversation_id})
        ON CREATE SET c.channel = $channel, c.started_at = $now
        CREATE (t:Turn {id: $turn_id, tool: $tool, args_json: $args_json,
                        verdict: $verdict, at: $now})
        CREATE (c)-[:HAS_TURN]->(t)
        WITH t
        OPTIONAL MATCH (r:Ruling {id: $ruling_id})
        FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END |
          CREATE (t)-[:PRODUCED]->(r)
        )
        RETURN t.id
        """,
        {
            "conversation_id": conversation_id,
            "channel": channel,
            "now": now,
            "turn_id": turn_id,
            "tool": tool,
            "args_json": json.dumps(args),
            "verdict": verdict or "",
            "ruling_id": ruling_id or "",
        },
    )
    return turn_id


def list_conversations(graph: str) -> list[dict[str, object]]:
    rows = as_rows(
        db.ro_query(
            graph,
            """
            MATCH (c:Conversation)-[:HAS_TURN]->(t:Turn)
            OPTIONAL MATCH (t)-[:PRODUCED]->(r:Ruling)
            WITH c, t, r ORDER BY t.at
            RETURN c.id AS id, c.started_at AS started_at,
                   collect({tool: t.tool, verdict: t.verdict, at: t.at, ruling_id: r.id}) AS turns
            """,
        )
    )
    return rows
