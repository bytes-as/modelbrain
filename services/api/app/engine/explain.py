"""Template and optional LLM phrasing. Never changes the verdict."""

from __future__ import annotations

from typing import Any

from app import llm
from app.engine.verdict import explain_template


async def explain_verdict(decided: dict[str, Any]) -> tuple[str, str]:
    """Return (explanation text, source: template|llm)."""
    if not llm.available():
        return explain_template(decided), "template"
    evidence = {
        "verdict": decided.get("verdict"),
        "declared_license": decided.get("declared_license"),
        "inherited_licenses": decided.get("inherited_licenses"),
        "blocking": decided.get("blocking"),
        "obligations": decided.get("obligations"),
        "incomplete_reasons": decided.get("incomplete_reasons"),
    }
    prompt = (
        "Phrase a 2-4 sentence explanation using ONLY this JSON evidence. "
        "Do not change the verdict field. End with: Automated screening, not legal advice.\n"
        f"{evidence}"
    )
    text = await llm.complete(prompt)
    if not text:
        return explain_template(decided), "template"
    return text, "llm"
