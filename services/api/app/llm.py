"""OpenRouter LLM gateway (G126). Optional everywhere: no key -> callers use templates.

One key, any model (LLM_MODEL). 6 s timeout, LLM_DAILY_BUDGET_CALLS per process per day.
The model only phrases text from evidence it is given; it never decides a verdict.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.config import get_settings

log = logging.getLogger("modelbrain.llm")
URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_S = 6.0
_budget = {"day": "", "calls": 0}


def available() -> bool:
    settings = get_settings()
    return bool(settings.openrouter_api_key and settings.llm_model)


def _spend() -> bool:
    today = time.strftime("%Y-%m-%d")
    if _budget["day"] != today:
        _budget.update(day=today, calls=0)
    if _budget["calls"] >= get_settings().llm_daily_budget_calls:
        return False
    _budget["calls"] += 1
    return True


async def complete(
    prompt: str, *, model: str | None = None, timeout_s: float = TIMEOUT_S
) -> str | None:
    """Return the model's text, or None (no key, budget spent, timeout or error)."""
    settings = get_settings()
    if not settings.openrouter_api_key or not (model or settings.llm_model) or not _spend():
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await asyncio.wait_for(
                client.post(
                    URL,
                    headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                    json={
                        "model": model or settings.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                ),
                timeout=timeout_s,
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"]).strip()
    except Exception as exc:
        log.warning("llm call failed: %s", type(exc).__name__)
        return None
