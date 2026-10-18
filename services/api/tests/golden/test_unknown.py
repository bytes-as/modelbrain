"""G039: unknown licence on the path yields CANNOT_DETERMINE."""

from uuid import uuid4

import pytest

from app.engine.verdict import verdict_from_graph
from app.graph import db
from tests.golden.helpers import EU_COMMERCIAL, model, write

CHILD = "demo/child-unknown-parent"
PARENT = "demo/parent-unknown-licence"


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g039_{uuid4().hex[:8]}"
    write(
        name,
        model(CHILD, "mit", "mit", root=False, parents=[(PARENT, "finetune")]),
    )
    write(name, model(PARENT, "", "unknown", root=False, parents=[]))
    yield name
    db.delete_graph(name)


def test_unknown_licence_cannot_determine(graph_name: str) -> None:
    decided = verdict_from_graph(CHILD, EU_COMMERCIAL, graph=graph_name)
    assert decided["verdict"] == "CANNOT_DETERMINE"
