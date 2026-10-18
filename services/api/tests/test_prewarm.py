"""G027: prewarm list includes demo set and eval models."""

from __future__ import annotations

from app.jobs.runner import prewarm_model_ids


def test_prewarm_includes_demo_and_eval_csv() -> None:
    ids = [model_id for model_id, _children in prewarm_model_ids()]
    assert "OPEA/Llama-3.2V-11B-cot-int4-sym-inc" in ids
    assert "Qwen/Qwen2.5-7B-Instruct" in ids
    assert len(ids) >= 40
