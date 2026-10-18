"""G032: parentless re-upload is incomplete in strict mode."""

from uuid import uuid4

import pytest

from app.engine.verdict import verdict_from_graph
from app.graph import db
from tests.golden.helpers import EU_COMMERCIAL, model, write

SIC = "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8"


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g032_{uuid4().hex[:8]}"
    write(
        name,
        model(
            SIC,
            "llama3.2",
            "llama3_2",
            root=False,
            parents=[],
            name_starts_with="Llama",
        ),
    )
    yield name
    db.delete_graph(name)


def test_strict_lineage_incomplete(graph_name: str) -> None:
    decided = verdict_from_graph(SIC, EU_COMMERCIAL, graph=graph_name, min_tier=2)
    assert decided["lineage_complete"] is False
    assert decided["verdict"] == "CANNOT_DETERMINE"
    assert any(SIC in reason for reason in decided["incomplete_reasons"])
