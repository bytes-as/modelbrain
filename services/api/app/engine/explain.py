"""Template and optional LLM phrasing. Never changes the verdict."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings
from app.engine.verdict import explain_template

log = logging.getLogger("modelbrain.explain")

_daily_calls = 0


async def explain_verdict(decided: dict[str, Any]) -> tuple[str, str]:
    """Return (explanation text, source: template|llm)."""
    settings = get_settings()
    if not settings.openrouter_api_key or not settings.llm_model:
        return explain_template(decided), "template"
    global _daily_calls
    if _daily_calls >= settings.llm_daily_budget_calls:
        return explain_template(decided), "template"
    try:
        text = await asyncio.wait_for(_llm_phrase(decided, settings), timeout=6.0)
        _daily_calls += 1
        return text, "llm"
    except Exception:
        log.warning("llm explain failed; using template")
        return explain_template(decided), "template"


async def _llm_phrase(decided: dict[str, Any], settings: Any) -> str:
    """Call OpenRouter with evidence-only prompt. Verdict is fixed in the payload."""
    import httpx

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
    async with httpx.AsyncClient(timeout=6.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"]).strip()
