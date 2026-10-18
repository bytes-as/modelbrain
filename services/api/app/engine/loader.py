"""Clause loader. Quotes come from the official source at runtime."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.engine.clauses import seed_path
from app.engine.quotes import extract_quote
from app.graph import db
from app.graph.queries import C1, C2, C5
from app.graph.rows import as_rows
from app.hf.client import HFClient, HubUnavailable
from app.ids import new_id

log = logging.getLogger("modelbrain.clauses")

stats: dict[str, int] = {"resolved": 0, "unresolved": 0}


def _json(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, separators=(",", ":"))


async def load_clauses(client: HFClient, *, graph: str = "hub") -> dict[str, int]:
    seed = json.loads(seed_path().read_text())
    split_regex = seed.get("split_regex") or r"\s+"
    resolved = 0
    unresolved = 0
    cache: dict[str, str | None] = {}
    stored = {
        str(row["id"]): row.get("quote") or ""
        for row in as_rows(db.ro_query(graph, C5))
        if row.get("id")
    }
    for licence in seed.get("licenses") or []:
        for clause in licence.get("clauses") or []:
            url = clause.get("source_raw_url")
            quote = None
            if url:
                if url not in cache:
                    cache[url] = await _fetch(client, url)
                body = cache[url]
                if body:
                    quote = extract_quote(
                        body,
                        source_format=clause.get("source_format") or "text",
                        split_regex=split_regex,
                        locator=clause.get("locator") or "",
                    )
            if not quote and stored.get(clause["id"]) and not (url and cache.get(url)):
                # Source unreachable: keep the quote we already verified.
                log.warning("clause source unreachable, keeping stored quote: %s", clause["id"])
                resolved += 1
                continue
            if quote:
                resolved += 1
            else:
                unresolved += 1
                log.warning("clause locator found nothing: %s", clause["id"])
            db.query(
                graph,
                C1,
                {
                    "license_key": licence["key"],
                    "name": licence.get("name") or licence["key"],
                    "url": licence.get("url") or "",
                    "id": clause["id"],
                    "kind": clause.get("kind") or "",
                    "effect": clause.get("effect") or "NEEDS_COUNSEL",
                    "applies_when": _json(clause.get("applies_when")),
                    "check": _json(clause.get("check")),
                    "summary": clause.get("summary") or "",
                    "quote": quote or "",
                    "locator": clause.get("locator") or "",
                    "source_url": clause.get("source_url") or "",
                    "source_raw_url": url or "",
                    "section": clause.get("section") or "",
                },
            )
    db.query(
        graph,
        C2,
        {
            "id": new_id("cl"),
            "now": int(time.time() * 1000),
            "resolved": resolved,
            "unresolved": unresolved,
        },
    )
    stats["resolved"] = resolved
    stats["unresolved"] = unresolved
    return dict(stats)


async def _fetch(client: HFClient, url: str) -> str | None:
    try:
        response = await client.get(url, ttl_s=7 * 24 * 60 * 60)
    except HubUnavailable:
        return None
    if response.status != 200:
        return None
    return response.body.decode("utf-8", "replace")
