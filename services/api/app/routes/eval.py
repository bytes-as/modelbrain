"""GET /api/eval serves eval/report.json when present."""

from __future__ import annotations

import json

from fastapi import APIRouter

from app.paths import repo_root

router = APIRouter()


@router.get("/api/eval")
def get_eval() -> dict:
    path = repo_root() / "eval" / "report.json"
    if not path.is_file():
        # Fall back to labels hash only so the page can still render.
        labels = repo_root() / "eval" / "labels.json"
        import hashlib

        sha = hashlib.sha256(labels.read_bytes()).hexdigest() if labels.is_file() else ""
        return {
            "labels_sha256": sha,
            "cases": 0,
            "false_allow": 0,
            "accuracy_default": 0,
            "rows": [],
            "note": "Run python eval/run_eval.py --api <url> to populate.",
        }
    return json.loads(path.read_text())
