"""G090/G091: the GitHub Action scanner and POST /api/ci/check."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "actions").is_dir())
spec = importlib.util.spec_from_file_location(
    "check", ROOT / "actions" / "modelbrain-check" / "check.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_scanner_finds_model_loads(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        'm = AutoModel.from_pretrained("OPEA/Llama-3.2V-11B-cot-int4-sym-inc")\n'
        "cfg = {'model_id': 'Qwen/Qwen2.5-7B-Instruct'}\n"
        "# see https://huggingface.co/datasets/foo/bar\n"
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.py").write_text('from_pretrained("ignored/model")')
    assert check.find_models(tmp_path) == [
        "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
        "Qwen/Qwen2.5-7B-Instruct",
    ]


def test_summary_marks_blocked_models() -> None:
    text = check.summary(
        {
            "results": [
                {
                    "model_id": "a/b",
                    "verdict": "BLOCKED",
                    "path": ["a/b", "c/d"],
                    "blocking": ["x.y"],
                }
            ]
        },
        "DE",
    )
    assert "🔴 BLOCKED" in text and "a/b → c/d" in text and "x.y" in text


def test_ci_check_rejects_bad_input() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    bad_country = client.post(
        "/api/ci/check", json={"model_ids": ["a/b"], "context": {"hq_country": "Germany"}}
    )
    assert bad_country.status_code == 422
    too_many = client.post(
        "/api/ci/check",
        json={"model_ids": [f"a/b{i}" for i in range(21)], "context": {"hq_country": "DE"}},
    )
    assert too_many.status_code == 422
