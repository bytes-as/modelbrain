"""ModelBrain GitHub Action: find Hugging Face model loads in a repo and ask ModelBrain (G090).

Standard library only. Exit codes: 0 pass, 1 a model is BLOCKED (or CANNOT_DETERMINE in
strict mode), 0 with a warning when the API is unreachable unless FAIL_ON_UNREACHABLE=true.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PATTERNS = [
    re.compile(r"""from_pretrained\(\s*["']([\w.-]+/[\w.-]+)["']"""),
    re.compile(
        r"""["']?\b(?:model|model_id|model_name|repo_id|base_model)["']?\s*[=:]\s*["']([\w.-]+/[\w.-]+)["']"""
    ),
    re.compile(r"""huggingface\.co/([\w.-]+/[\w.-]+)"""),
]
SUFFIXES = {".py", ".ipynb", ".yaml", ".yml", ".json", ".toml", ".cfg", ".md", ".txt"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
NOT_MODELS = {"datasets", "spaces", "docs", "blog", "api", "settings", "join"}


def find_models(root: Path) -> list[str]:
    found: dict[str, None] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in SUFFIXES or any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                model_id = match.group(1).rstrip(".")
                if model_id.split("/")[0].lower() not in NOT_MODELS:
                    found.setdefault(model_id, None)
    return list(found)


def ask(api: str, model_ids: list[str], hq: str, markets: list[str], commercial: bool, strict: bool):
    body = json.dumps(
        {
            "model_ids": model_ids[:20],
            "context": {"hq_country": hq, "markets": markets or [hq], "commercial": commercial},
            "strict": strict,
        }
    ).encode()
    request = urllib.request.Request(
        f"{api.rstrip('/')}/api/ci/check",
        data=body,
        method="POST",
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())


def summary(report: dict, hq: str) -> str:
    icon = {"BLOCKED": "🔴", "ALLOWED_WITH_OBLIGATIONS": "🟡", "ALLOWED": "🟢"}
    lines = [
        f"## ModelBrain check (HQ {hq})",
        "",
        "| Model | Verdict | Path | Blocking clauses |",
        "|---|---|---|---|",
    ]
    for row in report["results"]:
        verdict = row.get("verdict", "?")
        path = " → ".join(row.get("path") or [])
        blocking = ", ".join(row.get("blocking") or []) or "-"
        lines.append(f"| `{row['model_id']}` | {icon.get(verdict, '⚪')} {verdict} | {path} | {blocking} |")
    lines += ["", report.get("disclaimer", "Automated screening, not legal advice.")]
    return "\n".join(lines)


def main() -> int:
    api = os.environ.get("MODELBRAIN_API_URL", "")
    hq = os.environ.get("MODELBRAIN_HQ", "DE").upper()
    markets = [m.strip().upper() for m in os.environ.get("MODELBRAIN_MARKETS", "").split(",") if m.strip()]
    commercial = os.environ.get("MODELBRAIN_COMMERCIAL", "true").lower() == "true"
    strict = os.environ.get("MODELBRAIN_STRICT", "false").lower() == "true"
    fail_unreachable = os.environ.get("FAIL_ON_UNREACHABLE", "false").lower() == "true"
    root = Path(os.environ.get("MODELBRAIN_PATH", "."))
    if not api:
        print("::error::api_url is required")
        return 2
    models = find_models(root)
    if not models:
        print("ModelBrain: no Hugging Face model ids found.")
        return 0
    print(f"ModelBrain: checking {len(models)} model(s): {', '.join(models)}")
    try:
        report = ask(api, models, hq, markets, commercial, strict)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"::warning::ModelBrain API unreachable ({exc}); not failing the build.")
        return 1 if fail_unreachable else 0
    text = summary(report, hq)
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    for row in report["results"]:
        if row.get("verdict") == "BLOCKED":
            print(f"::error::{row['model_id']} is BLOCKED for HQ {hq}: {', '.join(row.get('blocking') or [])}")
    return 1 if report.get("fail") else 0


if __name__ == "__main__":
    sys.exit(main())
