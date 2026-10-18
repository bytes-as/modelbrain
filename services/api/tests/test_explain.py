"""G042: LLM phrasing never changes the verdict."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.engine.explain import explain_verdict
from app.engine.verdict import decide, explain_template


@pytest.mark.asyncio
async def test_mocked_llm_cannot_change_blocked_verdict() -> None:
    decided = decide(
        "demo/blocked",
        [
            {
                "ancestor": "demo/blocked",
                "hops": 0,
                "multimodal": True,
                "path": ["demo/blocked"],
                "tiers": [],
                "relations": [],
                "license": "llama3_2",
                "clauses": [
                    {
                        "id": "llama3_2.geo_eu_multimodal",
                        "kind": "k",
                        "effect": "BLOCK",
                        "applies_when": '{"always": true}',
                        "check": "",
                        "quote": "rights are not granted",
                        "source_url": "https://example.com",
                        "section": "1",
                    }
                ],
            }
        ],
        [],
        {
            "hq_country": "DE",
            "markets": ["DE"],
            "commercial": True,
            "mau": 0,
            "distributes_weights": False,
            "end_user_only": False,
        },
        {"declared_license": "apache-2.0"},
    )
    assert decided["verdict"] == "BLOCKED"
    with patch("app.llm.available", return_value=True):
        with patch(
            "app.llm.complete",
            new=AsyncMock(return_value="ALLOWED — you can ship this."),
        ):
            text, source = await explain_verdict(decided)
    assert decided["verdict"] == "BLOCKED"
    assert source == "llm"
    assert "ALLOWED" in text
    # The structured verdict is unchanged; only the prose came from the LLM.
    assert explain_template(decided).startswith("Verdict: BLOCKED")


@pytest.mark.asyncio
async def test_template_when_no_key_or_llm_fails() -> None:
    decided = {
        "verdict": "ALLOWED",
        "declared_license": "apache-2.0",
        "inherited_licenses": [],
        "blocking": [],
        "obligations": [],
        "needs_counsel": [],
        "incomplete_reasons": [],
    }
    with patch("app.llm.available", return_value=False):
        _text, source = await explain_verdict(decided)
    assert source == "template"
    with patch("app.llm.available", return_value=True):
        with patch("app.llm.complete", new=AsyncMock(return_value=None)):
            _text, source = await explain_verdict(decided)
    assert source == "template"
