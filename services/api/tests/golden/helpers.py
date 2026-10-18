"""Shared graph seeds for golden verdict tests."""

from __future__ import annotations

from app.agents.scout import write_parsed
from app.graph import db
from app.graph.queries import C1
from app.hf.parse import ParsedModel

EU_COMMERCIAL = {
    "hq_country": "DE",
    "markets": ["DE"],
    "commercial": True,
    "mau": 0,
    "distributes_weights": False,
    "end_user_only": False,
}


def model(
    model_id: str,
    declared: str,
    key: str,
    *,
    root: bool,
    multimodal: bool = False,
    parents: list[tuple[str, str]] = (),
    has_license_file: bool = True,
    name_starts_with: str = "Model",
) -> ParsedModel:
    return ParsedModel(
        model_id=model_id,
        sha="sha",
        declared_license=declared,
        license_key=key,
        pipeline_tag="image-text-to-text" if multimodal else "text-generation",
        created_at="2024-01-01",
        last_modified="2024-01-01",
        gated=False,
        is_root=root,
        multimodal=multimodal,
        card_has_llama_notice=False,
        has_license_file=has_license_file,
        name_starts_with=name_starts_with,
        parents=parents,
    )


def clause(
    graph: str,
    licence: str,
    name: str,
    clause_id: str,
    effect: str,
    applies: str,
    quote: str,
    *,
    check: str = "",
) -> None:
    db.query(
        graph,
        C1,
        {
            "license_key": licence,
            "name": name,
            "url": "https://example.com",
            "id": clause_id,
            "kind": "k",
            "effect": effect,
            "applies_when": applies,
            "check": check,
            "summary": clause_id,
            "quote": quote,
            "locator": "x",
            "source_url": f"https://example.com/{clause_id}",
            "source_raw_url": "https://example.com/raw",
            "section": "1",
        },
    )


def write(graph: str, parsed: ParsedModel, now_ms: int = 1) -> None:
    write_parsed(graph, parsed, now_ms)
