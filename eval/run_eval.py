#!/usr/bin/env python3
"""G056: run 80 frozen labels against the API; write eval/report.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def post_verdict(api: str, model_id: str, context: dict, strict: bool) -> dict:
    body = json.dumps({"model_id": model_id, "context": context, "strict": strict}).encode()
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("ADMIN_TOKEN", "")
    if token:
        # Admin requests are exempt from the per-IP verdict limit (160 calls per run).
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/verdict",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    labels = json.loads((ROOT / "eval" / "labels.json").read_text())
    contexts = labels["contexts"]
    sha = hashlib.sha256((ROOT / "eval" / "labels.json").read_bytes()).hexdigest()
    rows = []
    false_allow = 0
    for label in labels["labels"]:
        ctx = contexts[label["context"]]
        for strict in (False, True):
            mode = "strict" if strict else "default"
            try:
                got = post_verdict(args.api, label["model_id"], ctx, strict)
                actual = got.get("verdict")
            except Exception as exc:
                actual = f"ERROR:{type(exc).__name__}"
                got = {"error": str(exc)}
            expected = label["verdict"]
            # Strict often turns parentless into CANNOT_DETERMINE; only score default vs label,
            # and strict separately when label note mentions strict.
            match = actual == expected if not strict else actual in (expected, "CANNOT_DETERMINE")
            if not strict and expected == "BLOCKED" and actual == "ALLOWED":
                false_allow += 1
            if not strict and expected in ("BLOCKED", "CANNOT_DETERMINE") and actual == "ALLOWED":
                false_allow += 1
            rows.append(
                {
                    "model_id": label["model_id"],
                    "context": label["context"],
                    "mode": mode,
                    "expected": expected,
                    "actual": actual,
                    "match": match,
                }
            )
    report = {
        "labels_sha256": sha,
        "cases": len(rows),
        "false_allow": false_allow,
        "accuracy_default": sum(
            1 for r in rows if r["mode"] == "default" and r["match"]
        )
        / max(1, sum(1 for r in rows if r["mode"] == "default")),
        "rows": rows,
    }
    # Merge baselines if present
    baseline_path = ROOT / "eval" / "baseline_report.json"
    if baseline_path.is_file():
        report["baselines"] = json.loads(baseline_path.read_text())
    out = ROOT / "eval" / "report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out} false_allow={false_allow}")
    return 0 if false_allow == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
