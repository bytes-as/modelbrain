"""G097: the product never accuses anyone. Forbidden words stay out of UI and API copy."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "apps" / "web").is_dir())
FORBIDDEN = re.compile(r"violat|illegal|infring|stolen|leaked|\bfake\b|\bpirat", re.IGNORECASE)
SOURCES = [ROOT / "apps" / "web" / "app", ROOT / "services" / "api" / "app"]


def test_no_accusing_words_in_ui_or_api_copy() -> None:
    offenders: list[str] = []
    for base in SOURCES:
        for path in base.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"} or "node_modules" in path.parts:
                continue
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if FORBIDDEN.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:80]}")
    assert offenders == []
