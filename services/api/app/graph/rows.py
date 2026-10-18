"""Turn a FalkorDB result into a list of dicts."""

from __future__ import annotations

from typing import Any


def as_rows(result: Any) -> list[dict[str, Any]]:
    header = getattr(result, "header", None) or []
    names: list[str] = []
    for column in header:
        if isinstance(column, (list, tuple)):
            names.append(next(str(part) for part in column if isinstance(part, str)))
        else:
            names.append(str(column))
    rows: list[dict[str, Any]] = []
    for raw in getattr(result, "result_set", None) or []:
        if names and len(names) == len(raw):
            rows.append(dict(zip(names, raw, strict=True)))
        else:
            rows.append({str(index): value for index, value in enumerate(raw)})
    return rows
