"""Pydantic models matching docs/API.md Verdict / ClauseHit."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VerdictKind = Literal["ALLOWED", "ALLOWED_WITH_OBLIGATIONS", "BLOCKED", "CANNOT_DETERMINE"]


class ContextOut(BaseModel):
    hq_country: str
    markets: list[str]
    commercial: bool
    mau: int
    distributes_weights: bool
    end_user_only: bool


class ClauseHit(BaseModel):
    clause_id: str
    kind: str
    effect: Literal["BLOCK", "OBLIGATION", "NEEDS_COUNSEL"]
    license: str | None = None
    quote: str | None
    summary: str
    source_url: str
    section: str
    path: list[str]
    edge_tiers: list[int]
    relations: list[str]
    status: Literal["SATISFIED", "NOT_SATISFIED", "NOT_CHECKABLE"] | None = None


class PathOut(BaseModel):
    path: list[str]
    tiers: list[int]
    relations: list[str]
    method: str | None = None
    weights_sim: float | None = None
    share: float | None = None
    # Per-edge weight DNA evidence, aligned with `relations` (null when absent).
    methods: list[str | None] = []
    weights_sims: list[float | None] = []
    shares: list[float | None] = []


class VerdictOut(BaseModel):
    model_id: str
    verdict: VerdictKind
    strict: bool
    context: ContextOut
    declared_license: str | None
    declared_differs: bool
    inherited_licenses: list[str]
    blocking: list[ClauseHit]
    obligations: list[ClauseHit]
    needs_counsel: list[ClauseHit]
    lineage_complete: bool
    incomplete_reasons: list[str]
    alternatives: list[dict[str, str]]
    alternatives_message: str | None = None
    paths: list[PathOut]
    explanation: str
    explanation_source: Literal["llm", "template"]
    cypher: dict[str, str]
    ruling_id: str | None
    stale: bool
    disclaimer: Literal["Automated screening, not legal advice."]
    computed_ms: int = Field(ge=0)
