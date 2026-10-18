"""Scout: breadth-first ingest of a model and its ancestors into the hub."""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.graph import db
from app.graph.queries import I1, I2, I3, I4, I5
from app.hf.parse import ParsedModel, parse_model

Emit = Callable[[dict[str, object]], None]


class HubSource(Protocol):
    async def model(self, model_id: str) -> tuple[int, dict | None]: ...

    async def file_at_sha(
        self, model_id: str, sha: str, filename: str
    ) -> tuple[int, str | None]: ...

    async def children(self, model_id: str, relation: str, limit: int) -> list[str]: ...


@dataclass
class IngestResult:
    nodes: int = 0
    edges: int = 0
    incomplete_reasons: list[str] = field(default_factory=list)
    model_ids: list[str] = field(default_factory=list)


def _now_ms() -> int:
    return int(time.time() * 1000)


def write_parsed(graph: str, parsed: ParsedModel, now_ms: int) -> int:
    """Write I1–I5. Returns how many parent edges were written."""
    db.query(
        graph,
        I1,
        {
            "id": parsed.model_id,
            "sha": parsed.sha or "",
            "declared_license": parsed.declared_license or "",
            "pipeline_tag": parsed.pipeline_tag or "",
            "created_at": parsed.created_at or "",
            "last_modified": parsed.last_modified or "",
            "gated": parsed.gated,
            "is_root": parsed.is_root,
            "multimodal": parsed.multimodal,
            "now": now_ms,
            "card_has_llama_notice": parsed.card_has_llama_notice,
            "has_license_file": parsed.has_license_file,
            "name_starts_with": parsed.name_starts_with,
        },
    )
    sha = parsed.sha or ""
    snapshot_id = "@".join((parsed.model_id, sha))
    db.query(
        graph,
        I2,
        {
            "id": parsed.model_id,
            "snapshot_id": snapshot_id,
            "sha": sha,
            "declared_license": parsed.declared_license or "",
            "now": now_ms,
        },
    )
    db.query(
        graph,
        I3,
        {"id": parsed.model_id, "license_key": parsed.license_key, "sha": sha},
    )
    for fingerprint in parsed.fingerprints:
        db.query(
            graph,
            I5,
            {
                "key": fingerprint.key,
                "kind": fingerprint.kind,
                "value": fingerprint.value,
                "model_id": parsed.model_id,
            },
        )
    for parent, relation in parsed.parents:
        db.query(
            graph,
            I4,
            {"child": parsed.model_id, "parent": parent, "relation": relation},
        )
    return len(parsed.parents)


async def _load_one(
    source: HubSource,
    model_id: str,
    *,
    table: dict[str, str],
    roots: set[str],
) -> tuple[ParsedModel | None, str | None]:
    status, payload = await source.model(model_id)
    if status == 404 or payload is None:
        return None, f"{model_id} was not found on the Hugging Face Hub"
    if status in (401, 403):
        return None, f"{model_id} is private or gated at the model endpoint"
    readme = None
    config = None
    reasons: list[str] = []
    sha = str(payload.get("sha") or "")
    if sha:
        readme_status, readme_body = await source.file_at_sha(model_id, sha, "README.md")
        if readme_status in (401, 403, 404):
            reasons.append(f"README skipped: {readme_status}")
        else:
            readme = readme_body
        config_status, config_body = await source.file_at_sha(model_id, sha, "config.json")
        if config_status in (401, 403, 404):
            reasons.append(f"config skipped: {config_status}")
        elif config_body:
            try:
                loaded = json.loads(config_body)
                config = loaded if isinstance(loaded, dict) else None
            except json.JSONDecodeError:
                reasons.append("config skipped: not json")
    parsed = parse_model(
        model_id,
        payload,
        table=table,
        roots=roots,
        readme=readme,
        config=config,
        readme_skipped=next((item for item in reasons if item.startswith("README")), None),
        config_skipped=next((item for item in reasons if item.startswith("config")), None),
    )
    parsed.incomplete_reasons.extend(
        reason for reason in reasons if reason not in parsed.incomplete_reasons
    )
    return parsed, None


async def canonical_id(source: HubSource, model_id: str) -> str:
    """Renamed repos redirect (Meta-Llama-3.1-8B -> Llama-3.1-8B); key nodes by the Hub's own id."""
    try:
        status, payload = await source.model(model_id)
    except Exception:
        return model_id
    if status == 200 and payload:
        found = payload.get("id") or payload.get("modelId")
        if isinstance(found, str) and "/" in found:
            return found
    return model_id


async def ingest(
    model_id: str,
    source: HubSource,
    *,
    table: dict[str, str],
    roots: set[str],
    graph: str = "hub",
    children: bool = False,
    depth_cap: int = 6,
    node_cap: int = 300,
    child_cap: int = 25,
    emit: Emit | None = None,
) -> IngestResult:
    """BFS upward. children=True ingests one level of descendants of the start model only."""
    result = IngestResult()
    if emit:
        emit({"type": "started", "model_id": model_id})
    queue: deque[tuple[str, int]] = deque([(model_id, 0)])
    seen: set[str] = set()
    now_ms = _now_ms()
    while queue and len(seen) < node_cap:
        current, depth = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        parsed, missing = await _load_one(source, current, table=table, roots=roots)
        if missing:
            result.incomplete_reasons.append(missing)
            continue
        assert parsed is not None
        parsed.parents = [
            (await canonical_id(source, parent), relation) for parent, relation in parsed.parents
        ]
        result.edges += write_parsed(graph, parsed, now_ms)
        result.nodes += 1
        result.model_ids.append(current)
        result.incomplete_reasons.extend(parsed.incomplete_reasons)
        if emit:
            emit({"type": "node", "id": current})
        if depth < depth_cap:
            for parent, _relation in parsed.parents:
                if parent not in seen:
                    queue.append((parent, depth + 1))
        if children and current == model_id:
            for relation in ("finetune", "adapter", "merge", "quantized"):
                for child in await source.children(current, relation, child_cap):
                    if child in seen or len(seen) >= node_cap:
                        continue
                    child_parsed, child_missing = await _load_one(
                        source, child, table=table, roots=roots
                    )
                    seen.add(child)
                    if child_missing or child_parsed is None:
                        if child_missing:
                            result.incomplete_reasons.append(child_missing)
                        continue
                    result.edges += write_parsed(graph, child_parsed, now_ms)
                    db.query(
                        graph,
                        I4,
                        {"child": child, "parent": current, "relation": relation},
                    )
                    result.edges += 1
                    result.nodes += 1
                    result.model_ids.append(child)
                    if emit:
                        emit({"type": "node", "id": child})
    if len(seen) >= node_cap:
        result.incomplete_reasons.append("ingest cap reached")
    if emit:
        emit({"type": "done", "nodes": result.nodes})
    return result
