"""G013 and G014: no string-built Cypher, and every variable-length path is bounded."""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
QUERIES = APP / "graph" / "queries.py"

_CALL = re.compile(r"\.(?:ro_)?query\(")
_UNBOUNDED = re.compile(r"\*(?!\d+\.\.\d+)[\]\)]")


def _call_args(source: str, start: int) -> str:
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return source[start:]


def test_query_calls_are_not_string_built() -> None:
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        text = path.read_text()
        for match in _CALL.finditer(text):
            snippet = _call_args(text, match.end() - 1)
            built = (
                "f'" in snippet
                or 'f"' in snippet
                or "f'''" in snippet
                or 'f"""' in snippet
                or "+" in snippet
            )
            if built:
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.name}:{line}: {snippet.splitlines()[0]}")
    assert offenders == []


def test_variable_length_paths_are_bounded() -> None:
    text = QUERIES.read_text()
    assert _UNBOUNDED.findall(text) == []
