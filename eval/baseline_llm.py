"""G127: multi-LLM card-only baseline.

Each model in EVAL_BASELINE_MODELS (comma-separated OpenRouter ids) sees only what a scanner
reading the model card sees: the model id, its declared licence and the deployment context.
It must answer one of ALLOWED, ALLOWED_WITH_OBLIGATIONS, BLOCKED, CANNOT_DETERMINE. The report
compares each model with the frozen labels; the graph's own result is in eval/report.json.

  OPENROUTER_API_KEY=... EVAL_BASELINE_MODELS=anthropic/claude-sonnet-4.5,openai/gpt-4o \
    python3 -I eval/baseline_llm.py

Model ids are checked against GET https://openrouter.ai/api/v1/models before any call.
Without a key the script writes a skipped report and exits 0.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERDICTS = ("ALLOWED_WITH_OBLIGATIONS", "CANNOT_DETERMINE", "ALLOWED", "BLOCKED")
OUT = ROOT / "eval" / "baseline_llm_report.json"


def _post(key: str, model: str, prompt: str) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def _verdict(text: str) -> str:
    upper = text.upper()
    for verdict in VERDICTS:  # longest first, so ALLOWED_WITH_OBLIGATIONS wins over ALLOWED
        if re.search(rf"\b{verdict}\b", upper):
            return verdict
    return "UNPARSED"


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    models = [m.strip() for m in os.environ.get("EVAL_BASELINE_MODELS", "").split(",") if m.strip()]
    if not key or not models:
        OUT.write_text(json.dumps({"status": "skipped", "reason": "OPENROUTER_API_KEY or EVAL_BASELINE_MODELS not set"}, indent=2))
        print("skipped: set OPENROUTER_API_KEY and EVAL_BASELINE_MODELS")
        return 0
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as resp:
        known = {m["id"] for m in json.loads(resp.read())["data"]}
    unknown = [m for m in models if m not in known]
    if unknown:
        print(f"unknown OpenRouter model ids: {unknown}")
        return 2
    labels = json.loads((ROOT / "eval" / "labels.json").read_text())
    contexts = labels["contexts"]
    report: dict = {"labels_sha256": (ROOT / "eval" / "labels.sha256").read_text().strip(), "models": {}}
    for model in models:
        rows = []
        for label in labels["labels"]:
            ctx = contexts[label["context"]]
            prompt = (
                "You screen open model licences. Using ONLY the information below (you cannot see "
                "the model's lineage), answer with exactly one word: ALLOWED, "
                "ALLOWED_WITH_OBLIGATIONS, BLOCKED or CANNOT_DETERMINE.\n"
                f"Model: {label['model_id']}\nDeclared licence on the card: {label.get('declared_license')}\n"
                f"Company headquarters: {ctx['hq_country']}; markets: {ctx['markets']}; "
                f"commercial: {ctx['commercial']}; monthly active users: {ctx['mau']}."
            )
            try:
                answer = _verdict(_post(key, model, prompt))
            except Exception as exc:  # network, rate limit: record and continue
                answer = f"ERROR:{type(exc).__name__}"
            rows.append({"model_id": label["model_id"], "context": label["context"], "expected": label["verdict"], "actual": answer})
            time.sleep(0.2)
        matched = sum(1 for r in rows if r["actual"] == r["expected"])
        false_allow = sum(1 for r in rows if r["actual"].startswith("ALLOWED") and r["expected"] in ("BLOCKED", "CANNOT_DETERMINE"))
        report["models"][model] = {"cases": len(rows), "match_rate": matched / max(1, len(rows)), "false_allow": false_allow, "rows": rows}
        print(f"{model}: match {matched}/{len(rows)}, false ALLOW {false_allow}")
    OUT.write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
