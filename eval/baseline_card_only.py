#!/usr/bin/env python3
"""G057: declared-licence-only baseline (+ optional LLM when OPENROUTER_API_KEY is set)."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Minimal card-only rules: if declared licence maps to known BLOCK when commercial, else ALLOWED.
BLOCK_IF_COMMERCIAL = {"cc-by-nc-4.0", "llama3_2", "llama3", "gemma", "other", "unknown"}


def decide_card(declared: str | None, commercial: bool) -> str:
    key = (declared or "unknown").lower()
    if key in BLOCK_IF_COMMERCIAL and commercial:
        if key in {"llama3_2", "llama3", "gemma"}:
            return "ALLOWED_WITH_OBLIGATIONS"  # card-only cannot see EU multimodal
        if key in {"other", "unknown"}:
            return "CANNOT_DETERMINE"
        return "BLOCKED"
    if key in {"llama3_2", "llama3", "gemma"}:
        return "ALLOWED_WITH_OBLIGATIONS"
    return "ALLOWED"


def main() -> None:
    labels = json.loads((ROOT / "eval" / "labels.json").read_text())
    contexts = labels["contexts"]
    rows = []
    for label in labels["labels"]:
        ctx = contexts[label["context"]]
        card = decide_card(label.get("declared_license"), bool(ctx.get("commercial")))
        rows.append(
            {
                "model_id": label["model_id"],
                "context": label["context"],
                "card_only": card,
                "label": label["verdict"],
                "match_label": card == label["verdict"],
            }
        )
    report = {
        "declared_licence_only": {
            "cases": len(rows),
            "match_rate": sum(1 for r in rows if r["match_label"]) / max(1, len(rows)),
            "rows": rows,
        },
        "llm_card_only": None,
    }
    if os.environ.get("OPENROUTER_API_KEY") and os.environ.get("LLM_MODEL"):
        report["llm_card_only"] = {
            "status": "skipped",
            "reason": "live LLM baseline optional; run manually if needed",
        }
    else:
        report["llm_card_only"] = {"status": "skipped", "reason": "no OPENROUTER_API_KEY"}
    out = ROOT / "eval" / "baseline_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
