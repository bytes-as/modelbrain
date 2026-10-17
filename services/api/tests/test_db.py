"""G010: FalkorDB helpers against the service container."""

from uuid import uuid4

import pytest

from app.graph import db


@pytest.fixture(autouse=True)
def _fresh_connection() -> None:
    db._db = None
    db.connect(tries=5, delay_s=0.5)


def test_connect_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"n": 0}
    real = db._client

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("down")
        return real()

    monkeypatch.setattr(db, "_client", flaky)
    db._db = None
    db.connect(tries=5, delay_s=0)
    assert attempts["n"] == 3


def test_connect_stops_after_the_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    def always_down():
        raise ConnectionError("down")

    monkeypatch.setattr(db, "_client", always_down)
    db._db = None
    with pytest.raises(ConnectionError):
        db.connect(tries=3, delay_s=0)


def test_parameterised_query_and_ro_query() -> None:
    name = f"g010_{uuid4().hex[:8]}"
    try:
        db.query(name, "CREATE (:Probe {id: $id})", {"id": "p1"})
        result = db.ro_query(name, "MATCH (n:Probe {id: $id}) RETURN n.id", {"id": "p1"})
        assert result.result_set == [["p1"]]
    finally:
        db.delete_graph(name)


def test_graph_copy_and_reject_existing_destination() -> None:
    source = f"g010s_{uuid4().hex[:8]}"
    destination = f"g010d_{uuid4().hex[:8]}"
    try:
        db.query(source, "CREATE (:Probe {id: $id})", {"id": "copied"})
        db.copy_graph(source, destination)
        copied = db.ro_query(destination, "MATCH (n:Probe) RETURN n.id")
        assert copied.result_set == [["copied"]]
        with pytest.raises(Exception):
            db.copy_graph(source, destination)
    finally:
        for name in (source, destination):
            try:
                db.delete_graph(name)
            except Exception:
                pass
