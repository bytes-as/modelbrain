"""G011: queries.py matches docs/queries.cypher after whitespace normalisation."""

from __future__ import annotations

import re
from pathlib import Path

from app.graph.queries import QUERIES


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "queries.cypher").is_file():
            return parent
    raise FileNotFoundError("docs/queries.cypher")


ROOT = _repo_root()
HEADER = re.compile(r"^//\s+((?:SCHEMA|[IQRDPTOALC]\d+|W\d+B?))\b")
EXPECTED = (
    "SCHEMA",
    "I1",
    "I2",
    "I3",
    "I4",
    "I5",
    "Q1",
    "Q2",
    "Q3",
    "R1",
    "R2",
    "R3",
    "D1",
    "D2",
    "D3",
    "P1",
    "T1",
    "T2",
    "T3",
    "T4",
    "T5",
    "T9",
    "T10",
    "T6",
    "T7",
    "T8",
    "A1",
    "A2",
    "A3",
    "A4",
    "A5",
    "O1",
    "O2",
    "O3",
    "O4",
    "O5",
    "L1",
    "L2",
    "C1",
    "C2",
    "C3",
    "C4",
    "W0",
    "W1",
    "W1B",
    "W2",
    "W3",
    "W4",
    "W5",
    "W6",
    "W7",
    "W8",
    "W9",
)


def _norm(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _blocks(text: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        body = "\n".join(buf).strip("\n")
        if current and body.strip():
            blocks.setdefault(current, []).append(body.strip("\n"))
        buf = []

    for line in text.splitlines():
        match = HEADER.match(line)
        if match:
            flush()
            current = match.group(1)
            continue
        if line.startswith("//"):
            continue
        if current is not None:
            buf.append(line)
    flush()
    return {name: "\n\n".join(parts) for name, parts in blocks.items()}


def test_every_named_query_matches_the_cypher_file() -> None:
    source = (ROOT / "docs" / "queries.cypher").read_text()
    blocks = _blocks(source)
    assert tuple(QUERIES) == EXPECTED
    assert set(blocks) == set(EXPECTED)
    for name in EXPECTED:
        assert _norm(QUERIES[name]) == _norm(blocks[name]), name
