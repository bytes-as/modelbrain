"""Locate the repository root, where data/ and docs/ live."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "clauses.seed.json").is_file():
            return parent
    packaged = Path("/app/data/clauses.seed.json")
    if packaged.is_file():
        return Path("/app")
    raise FileNotFoundError("data/clauses.seed.json")
