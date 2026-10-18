"""G041: BLOCKED verdicts include alternatives from the candidate set or the exact message."""

from uuid import uuid4

import pytest

from app.engine.verdict import verdict_from_graph
from app.graph import db
from tests.golden.helpers import EU_COMMERCIAL, clause, model, write

OPEA = "OPEA/Llama-3.2V-11B-cot-int4-sym-inc"
XKEV = "Xkev/Llama-3.2V-11B-cot"
META = "meta-llama/Llama-3.2-11B-Vision-Instruct"
QWEN = "Qwen/Qwen2.5-VL-7B-Instruct"


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g041_{uuid4().hex[:8]}"
    write(
        name,
        model(
            OPEA,
            "apache-2.0",
            "apache-2.0",
            root=False,
            multimodal=True,
            parents=[(XKEV, "quantized")],
        ),
    )
    write(
        name,
        model(
            XKEV,
            "apache-2.0",
            "apache-2.0",
            root=False,
            multimodal=True,
            parents=[(META, "finetune")],
        ),
    )
    write(name, model(META, "llama3.2", "llama3_2", root=True, multimodal=True))
    write(name, model(QWEN, "apache-2.0", "apache-2.0", root=True, multimodal=True))
    clause(
        name,
        "llama3_2",
        "Llama 3.2",
        "llama3_2.geo_eu_multimodal",
        "BLOCK",
        '{"all":[{"hq_in":"EU"},{"ancestor_multimodal":true},{"not":{"end_user_only":true}}]}',
        "rights are not granted in the European Union",
    )
    yield name
    db.delete_graph(name)


def test_blocked_includes_alternative_or_message(graph_name: str) -> None:
    decided = verdict_from_graph(OPEA, EU_COMMERCIAL, graph=graph_name)
    assert decided["verdict"] == "BLOCKED"
    assert decided["alternatives"] or decided["alternatives_message"] == (
        "No compliant alternative in our candidate set"
    )
    if decided["alternatives"]:
        assert any(item["model_id"] == QWEN for item in decided["alternatives"])
