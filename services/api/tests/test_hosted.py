"""G128-G130: hosted path in the graph, residency proof, and the hosted licence nuance."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.engine import hosted
from app.graph import db
from app.graph.queries import O1, O2, O3


@pytest.fixture()
def hub():
    db.connect(tries=5, delay_s=0.5)
    name = f"hosted_{uuid4().hex[:8]}"
    yield name
    db.delete_graph(name)


def _seed(hub: str) -> None:
    for slug, hq, dcs in [("eu-host", "DE", ["DE", "FR"]), ("us-host", "US", ["US"])]:
        db.query(
            hub,
            O1,
            {
                "slug": slug,
                "name": slug,
                "hq": hq,
                "datacenters": dcs,
                "tos_url": None,
                "privacy_url": None,
                "now": 1,
            },
        )
    db.query(
        hub,
        O2,
        {
            "or_id": "meta/llama-small",
            "name": "Llama small",
            "hf_id": "meta-llama/Llama-3.2-1B-Instruct",
            "now": 1,
        },
    )
    db.query(
        hub,
        O2,
        {
            "or_id": "meta/llama-vision",
            "name": "Llama vision",
            "hf_id": "meta-llama/Llama-3.2-11B-Vision-Instruct",
            "now": 1,
        },
    )
    for or_id, slug in [
        ("meta/llama-small", "eu-host"),
        ("meta/llama-small", "us-host"),
        ("meta/llama-vision", "us-host"),
    ]:
        db.query(
            hub,
            O3,
            {
                "or_id": or_id,
                "provider_slug": slug,
                "quantization": "bf16",
                "tag": slug,
                "status": 0,
                "uptime_30m": 99.0,
            },
        )


def test_residency_proof_with_and_without_an_eu_provider(hub: str) -> None:
    _seed(hub)
    ok = asyncio.run(
        hosted.where_can_i_run("meta-llama/Llama-3.2-1B-Instruct", "EU", hub, refresh=False)
    )
    assert ok["residency"]["ok"] is True
    assert [p["provider"] for p in ok["hosted"][0]["allowed"]] == ["eu-host"]
    none = asyncio.run(
        hosted.where_can_i_run("meta-llama/Llama-3.2-11B-Vision-Instruct", "EU", hub, refresh=False)
    )
    assert none["residency"]["ok"] is False
    assert none["residency"]["proof"] == "no provider serves this model from an allowed datacenter"
    assert none["residency"]["unverified_providers"] == []
    assert {p["slug"] for p in none["hosted"][0]["providers"]} == {"us-host"}


def test_hosted_use_turns_the_eu_multimodal_block_into_needs_counsel() -> None:
    decided = {
        "verdict": "BLOCKED",
        "blocking": [
            {"clause_id": "llama3_2.geo_eu_multimodal", "effect": "BLOCK", "summary": "x"}
        ],
        "obligations": [{"clause_id": "llama3_2.aup"}],
        "needs_counsel": [],
    }
    through_provider = hosted.hosted_adjust(dict(decided), end_user_only=False)
    assert through_provider["verdict"] == "CANNOT_DETERMINE"
    assert through_provider["needs_counsel"][0]["effect"] == "NEEDS_COUNSEL"
    end_user = hosted.hosted_adjust(dict(decided), end_user_only=True)
    assert end_user["verdict"] == "ALLOWED_WITH_OBLIGATIONS"


def test_eu_country_list() -> None:
    countries = hosted.eu_countries()
    assert len(countries) == 27 and "DE" in countries and "GB" not in countries
