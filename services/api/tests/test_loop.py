"""G080/G083/G084/G085/G086: fan-out reopen, Xkev replay, compounding and hub privacy."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.engine import watcher
from app.graph import db
from app.graph.rows import as_rows


@pytest.fixture()
def graphs():
    db.connect(tries=5, delay_s=0.5)
    suffix = uuid4().hex[:8]
    names = {"hub": f"hubt_{suffix}", "a": f"tenant_t_a_{suffix}", "b": f"tenant_t_b_{suffix}"}
    yield names
    for name in names.values():
        try:
            db.delete_graph(name)
        except Exception:
            pass


def _hub(hub: str) -> None:
    db.query(
        hub,
        "CREATE (root:Model {id:'meta/root', is_root:true, card_has_llama_notice:true}),"
        " (mid:Model {id:'up/mid', card_has_llama_notice:false}),"
        " (leaf:Model {id:'down/leaf', card_has_llama_notice:false}),"
        " (lone:Model {id:'other/lone'}),"
        " (mid)-[:DERIVED_FROM {relation:'finetune', source:'declared', tier:2}]->(root),"
        " (leaf)-[:DERIVED_FROM {relation:'quantized', source:'declared', tier:2}]->(mid),"
        " (lone)-[:DERIVED_FROM {relation:'inferred', source:'inferred', tier:1, confirmations:0,"
        " confirmers:[]}]->(root)",
    )


def _company(graph: str, model_id: str, person: str) -> None:
    db.query(
        graph,
        "CREATE (p:Person {id:$person, name:'Test Owner (fictional)'}),"
        " (d:Deployment {id:$dep, model_id:$model}),"
        " (r:Ruling {id:$ruling, verdict:'BLOCKED', created_at:1}),"
        " (f:Fact {id:$fact, model_id:$model}),"
        " (p)-[:OWNS]->(d), (r)-[:FOR]->(d), (r)-[:RESTS_ON]->(f)",
        {
            "person": person,
            "dep": f"dep_{person}",
            "model": model_id,
            "ruling": f"rul_{person}",
            "fact": f"fact_{person}",
        },
    )


def test_fan_out_reopens_rulings_on_descendants(graphs) -> None:
    _hub(graphs["hub"])
    _company(graphs["a"], "down/leaf", "alice")
    report = watcher.fan_out(
        "up/mid", "licence file added", graphs=[graphs["a"]], hub=graphs["hub"]
    )
    assert report["descendants"] == 1
    assert report["not_inherited"] == 1  # fix leverage: the child lacks the notice
    assert [r["ruling_id"] for r in report["reopened"]] == ["rul_alice"]
    tasks = as_rows(
        db.ro_query(
            graphs["a"],
            "MATCH (t:Task {kind:'REVIEW_RULING'})-[:ASSIGNED_TO]->(p:Person) RETURN p.id AS owner",
        )
    )
    assert tasks == [{"owner": "alice"}]
    events = as_rows(
        db.ro_query(
            graphs["a"], "MATCH (e:Event {kind:'REOPENED'})-[:ON]->(r:Ruling) RETURN r.id AS id"
        )
    )
    assert events == [{"id": "rul_alice"}]
    audit = watcher.recent_fan_outs(5, hub=graphs["hub"])
    assert audit[0]["model_id"] == "up/mid" and audit[0]["reopened"] == 1


def test_fan_out_ignores_unrelated_rulings(graphs) -> None:
    _hub(graphs["hub"])
    _company(graphs["a"], "other/lone", "alice")
    report = watcher.fan_out("up/mid", "change", graphs=[graphs["a"]], hub=graphs["hub"])
    assert report["reopened"] == []


def test_two_independent_confirmations_raise_the_tier(graphs) -> None:
    _hub(graphs["hub"])
    _company(graphs["a"], "other/lone", "alice")
    _company(graphs["b"], "other/lone", "bob")
    first = watcher.confirm_edge(graphs["a"], "other/lone", "meta/root", "alice", hub=graphs["hub"])
    assert first["ok"] and first["tier_after"] == 1 and first["confirmations"] == 1
    again = watcher.confirm_edge(graphs["a"], "other/lone", "meta/root", "alice", hub=graphs["hub"])
    assert again["confirmations"] == 1  # the same company never counts twice
    second = watcher.confirm_edge(graphs["b"], "other/lone", "meta/root", "bob", hub=graphs["hub"])
    assert second["tier_before"] == 1 and second["tier_after"] == 3
    assert second["confirmations"] == 2
    assert "fan_out" in second


def test_hub_never_stores_tenant_names(graphs) -> None:
    _hub(graphs["hub"])
    _company(graphs["a"], "other/lone", "alice")
    watcher.confirm_edge(graphs["a"], "other/lone", "meta/root", "alice", hub=graphs["hub"])
    rows = as_rows(
        db.ro_query(
            graphs["hub"],
            "MATCH ()-[e:DERIVED_FROM]->() RETURN e.confirmers AS c",
        )
    )
    stored = " ".join(str(r["c"]) for r in rows)
    assert graphs["a"] not in stored and "alice" not in stored
    assert watcher.tenant_hash(graphs["a"]) in stored


def test_unknown_person_is_refused(graphs) -> None:
    _hub(graphs["hub"])
    _company(graphs["a"], "other/lone", "alice")
    result = watcher.confirm_edge(
        graphs["a"], "other/lone", "meta/root", "mallory", hub=graphs["hub"]
    )
    assert result["ok"] is False


def test_replay_data_is_the_real_history() -> None:
    data = watcher.replay_data()
    assert data["fix"]["commit"] == "e8c2529775"
    assert data["fix"]["days_after_report"] == 130
    assert len(data["children"]) == 9
