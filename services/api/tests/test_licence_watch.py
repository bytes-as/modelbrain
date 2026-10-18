"""G132-G134: licence text watch reopens rulings; linked custom licences resolve; fetcher backends."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import pytest

from app.engine import licence_watch
from app.fetch import Fetcher
from app.graph import db
from app.graph.rows import as_rows


class FakeFetcher:
    def __init__(self, texts: dict[str, str]) -> None:
        self.texts = texts

    async def text(self, url: str) -> str | None:
        return self.texts.get(url, "unchanged licence text")

    async def aclose(self) -> None:
        return None


@pytest.fixture()
def graphs():
    db.connect(tries=5, delay_s=0.5)
    names = {"hub": f"lw_{uuid4().hex[:8]}", "t": f"tenant_lw_{uuid4().hex[:8]}"}
    yield names
    for name in names.values():
        try:
            db.delete_graph(name)
        except Exception:
            pass


def test_text_change_reopens_rulings_resting_on_its_clauses(graphs) -> None:
    sources = licence_watch.sources()
    url, clause_ids = next(iter(sources.items()))
    db.query(graphs["hub"], "CREATE (:Marker)")
    db.query(
        graphs["t"],
        "CREATE (p:Person {id:'owner'}), (d:Deployment {id:'dep'}), (r:Ruling {id:'rul', created_at:1}),"
        " (f:Fact {id:'f', clause_ids:$cids}), (p)-[:OWNS]->(d), (r)-[:FOR]->(d), (r)-[:RESTS_ON]->(f)",
        {"cids": [clause_ids[0]]},
    )
    first = asyncio.run(licence_watch.run_watch(FakeFetcher({}), graphs["hub"], [graphs["t"]]))
    assert first["baseline"] == first["sources"] == len(sources) and first["reopened"] == 0
    again = asyncio.run(licence_watch.run_watch(FakeFetcher({}), graphs["hub"], [graphs["t"]]))
    assert again["changed"] == [] and again["reopened"] == 0
    changed = asyncio.run(
        licence_watch.run_watch(
            FakeFetcher({url: "a new version of the licence"}), graphs["hub"], [graphs["t"]]
        )
    )
    assert [c["url"] for c in changed["changed"]] == [url]
    assert changed["reopened"] == 1
    tasks = as_rows(
        db.ro_query(graphs["t"], "MATCH (t:Task {kind:'REVIEW_RULING'}) RETURN count(t) AS n")
    )
    assert tasks[0]["n"] == 1


def test_custom_licence_text_matches_by_locators() -> None:
    phrases = licence_watch.locators()["llama3_2"]
    text = "LLAMA 3.2 COMMUNITY LICENSE AGREEMENT. " + " ... ".join(phrases[:2]) + " ... end."
    assert licence_watch.match_licence(text) == "llama3_2"
    # Generic clause wording without the licence's own name is not a match.
    assert licence_watch.match_licence("Our own licence. " + " ... ".join(phrases[:3])) is None
    assert licence_watch.match_licence("An entirely bespoke licence with its own terms.") is None


def test_httpx_fetcher_strips_html_and_handles_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ok":
            return httpx.Response(200, html="<html><style>x</style><p>Licence   text</p></html>")
        return httpx.Response(404)

    fetcher = Fetcher(backend="httpx", transport=httpx.MockTransport(handler))
    try:
        assert asyncio.run(fetcher.text("https://example.invalid/ok")) == "Licence text"
        assert asyncio.run(fetcher.text("https://example.invalid/missing")) is None
    finally:
        asyncio.run(fetcher.aclose())


def test_unwired_backend_falls_back_to_httpx() -> None:
    assert Fetcher(backend="anakin").backend == "httpx"
