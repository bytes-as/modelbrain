"""G034: decision order, including a null quote counting as needs counsel."""

from app.engine.verdict import decide

CONTEXT = {
    "hq_country": "DE",
    "markets": ["DE"],
    "commercial": True,
    "mau": 0,
    "distributes_weights": False,
    "end_user_only": False,
}


def _row(
    licence: str,
    effect: str,
    clause_id: str,
    *,
    hops: int = 1,
    quote: str | None = "quoted",
    multimodal: bool = False,
) -> dict:
    return {
        "ancestor": "parent/model" if hops else "child/model",
        "is_root": hops == 0,
        "multimodal": multimodal,
        "hops": hops,
        "path": ["child/model", "parent/model"][: hops + 1],
        "tiers": [2] if hops else [],
        "relations": ["finetune"] if hops else [],
        "license": licence,
        "clauses": [
            {
                "id": clause_id,
                "kind": "k",
                "effect": effect,
                "applies_when": '{"always": true}',
                "check": None,
                "quote": quote,
                "source_url": "https://example.com",
                "section": "1",
            }
        ],
    }


def test_block_wins() -> None:
    rows = [
        _row("apache-2.0", "OBLIGATION", "ob", hops=0),
        _row("llama3_2", "BLOCK", "block", multimodal=True),
    ]
    decided = decide("child/model", rows, [{"top": "parent/model", "is_root": True}], CONTEXT, {})
    assert decided["verdict"] == "BLOCKED"


def test_null_quote_is_needs_counsel() -> None:
    rows = [_row("llama3_2", "BLOCK", "block", quote=None)]
    rows.insert(0, _row("apache-2.0", "OBLIGATION", "ob", hops=0, quote="q"))
    decided = decide("child/model", rows, [{"top": "parent/model", "is_root": True}], CONTEXT, {})
    assert decided["verdict"] == "CANNOT_DETERMINE"
    assert decided["needs_counsel"][0]["clause_id"] == "block"


def test_incomplete_lineage() -> None:
    rows = [_row("apache-2.0", "OBLIGATION", "ob", hops=0)]
    decided = decide("child/model", rows, [{"top": "child/model", "is_root": False}], CONTEXT, {})
    assert decided["verdict"] == "CANNOT_DETERMINE"
    assert decided["lineage_complete"] is False


def test_obligations_then_allowed() -> None:
    obligation = decide(
        "child/model",
        [_row("llama3_2", "OBLIGATION", "notice", hops=0)],
        [{"top": "child/model", "is_root": True}],
        CONTEXT,
        {},
    )
    assert obligation["verdict"] == "ALLOWED_WITH_OBLIGATIONS"
    allowed = decide(
        "child/model",
        [_row("apache-2.0", "OBLIGATION", "ship", hops=0, quote="q")],
        [{"top": "child/model", "is_root": True}],
        CONTEXT,
        {},
    )
    # The obligation applies because applies_when is always. Use a non-applicable clause for ALLOWED.
    allowed = decide(
        "child/model",
        [
            {
                **_row("apache-2.0", "OBLIGATION", "ship", hops=0),
                "clauses": [
                    {
                        "id": "ship",
                        "kind": "k",
                        "effect": "OBLIGATION",
                        "applies_when": '{"distributes_weights": true}',
                        "check": None,
                        "quote": "q",
                        "source_url": "https://example.com",
                        "section": "4",
                    }
                ],
            }
        ],
        [{"top": "child/model", "is_root": True}],
        CONTEXT,
        {},
    )
    assert allowed["verdict"] == "ALLOWED"
