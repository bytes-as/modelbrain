"""G088: notices are drafted, never posted without approval, and only posted to allowlisted repos."""

from __future__ import annotations

import asyncio
import json
import random
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from app.agents import notifier
from app.engine import dna
from app.graph import db
from app.hf.dna import OK, DnaResult


@pytest.fixture()
def hub():
    db.connect(tries=5, delay_s=0.5)
    name = f"notice_{uuid4().hex[:8]}"
    rng = random.Random(3)
    base = [rng.uniform(-1, 1) for _ in range(1024)]
    db.query(
        name,
        "CREATE (:Model {id:'meta/base', created_at:'2024-01-01', is_root:true})-[:DECLARES]->(:License {key:'llama3_1'}),"
        " (:Model {id:'x/relabel', created_at:'2025-01-01', declared_license:'mit'})",
    )
    dna.ensure_index(name)
    for mid, vec in [("meta/base", base), ("x/relabel", [v + rng.gauss(0, 0.02) for v in base])]:
        dna.write_result(name, mid, DnaResult(OK, vector=vec, sig="h|L|i"))
    yield name
    db.delete_graph(name)


def test_draft_is_neutral_and_waits_for_approval(hub: str) -> None:
    draft = asyncio.run(notifier.draft_for("x/relabel", hub=hub))
    assert draft["state"] == "AWAITING_APPROVAL"
    assert "meta/base" in draft["body"] and "llama3_1" in draft["body"]
    assert notifier.SIGNATURE in draft["body"]
    for word in ("violat", "illegal", "stolen", "leaked", "infring"):
        assert word not in draft["body"].lower()


def test_outside_the_allowlist_nothing_is_posted(hub: str) -> None:
    draft = asyncio.run(notifier.draft_for("x/relabel", hub=hub))
    with patch.object(notifier, "get_settings") as settings:
        settings.return_value.hf_post_allowlist = ["someone/else"]
        settings.return_value.hf_write_token = "hf_test"
        result = asyncio.run(notifier.approve(draft["id"], hub=hub))
    assert result["state"] == "READY_TO_COPY" and result["posted_url"] is None


def test_allowlisted_repo_is_posted_through_the_discussions_api(hub: str) -> None:
    draft = asyncio.run(notifier.draft_for("x/relabel", target_repo="us/loop-test", hub=hub))
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"num": 7})

    with patch.object(notifier, "get_settings") as settings:
        settings.return_value.hf_post_allowlist = ["us/loop-test"]
        settings.return_value.hf_write_token = "hf_test"
        result = asyncio.run(
            notifier.approve(draft["id"], hub=hub, transport=httpx.MockTransport(handler))
        )
    assert seen["url"] == "https://huggingface.co/api/models/us/loop-test/discussions"
    assert seen["body"]["title"] and seen["body"]["pullRequest"] is False
    assert seen["auth"] == "Bearer hf_test"
    assert result["state"] == "POSTED"
    assert result["posted_url"] == "https://huggingface.co/us/loop-test/discussions/7"
