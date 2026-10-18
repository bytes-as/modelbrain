"""Live loop on our own test repo (G089, FLOWS F10.4). Standard library only.

1. Create (or reuse) a public test repo with a README only: "test fixture, contains no weights",
   declaring apache-2.0 and no base model.
2. ModelBrain checks it (baseline), drafts a notice, and a human approval posts it as a
   discussion (the repo is on HF_POST_ALLOWLIST).
3. The author (us) edits the card to declare the base model and its licence.
4. "Check now" re-reads the repo, diffs it and fans out; the author's declaration is promoted
   to tier 4 and the discussion gets an Outcome.

  HF_WRITE_TOKEN=... ADMIN_TOKEN=... python3 -I scripts/live_loop.py --repo user/modelbrain-loop-test

Tokens come from the environment and are never printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request

HUB = "https://huggingface.co"
BASE = "meta-llama/Llama-3.2-1B"

README_V1 = """---
license: apache-2.0
tags:
- test-fixture
---
# ModelBrain loop test

Test fixture for the ModelBrain hackathon demo. **This repository contains no weights.**
It exists so ModelBrain can post a discussion to a repo we own and watch the card change.
"""

README_V2 = f"""---
license: llama3.2
base_model: {BASE}
tags:
- test-fixture
---
# ModelBrain loop test

Test fixture for the ModelBrain hackathon demo. **This repository contains no weights.**
Updated after the ModelBrain discussion: the card now declares its base model ({BASE})
and the upstream licence (Llama 3.2 Community License).
"""


def _req(method: str, url: str, token: str, body: bytes | None = None, ctype: str = "application/json"):
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw and raw[:1] in b"{[" else raw.decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")[:300]


def hf_commit(token: str, repo: str, readme: str, summary: str) -> int:
    lines = [
        {"key": "header", "value": {"summary": summary, "description": ""}},
        {"key": "file", "value": {"content": base64.b64encode(readme.encode()).decode(), "path": "README.md", "encoding": "base64"}},
    ]
    body = "\n".join(json.dumps(line) for line in lines).encode()
    status, _ = _req("POST", f"{HUB}/api/models/{repo}/commit/main", token, body, "application/x-ndjson")
    return status


def api(method: str, path: str, admin: str, payload: dict | None = None, base: str = "http://localhost:8000"):
    body = json.dumps(payload).encode() if payload is not None else None
    return _req(method, f"{base}{path}", admin, body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    hf, admin = os.environ.get("HF_WRITE_TOKEN", ""), os.environ.get("ADMIN_TOKEN", "")
    if not hf or not admin:
        print("set HF_WRITE_TOKEN and ADMIN_TOKEN")
        return 2
    owner, name = args.repo.split("/")
    status, body = _req("POST", f"{HUB}/api/repos/create", hf, json.dumps({"name": name, "type": "model", "private": False}).encode())
    print("1. create repo:", status, "(409 = already exists)" if status == 409 else "")
    if status not in (200, 201, 409):
        print("   ", body)
        return 1
    print("   README v1 commit:", hf_commit(hf, args.repo, README_V1, "Test fixture: README only, no weights"))
    time.sleep(3)
    status, base = api("POST", "/api/watch/check", admin, {"model_id": args.repo}, args.api)
    print("2. baseline check:", status, {k: base.get(k) for k in ("changed", "sha")} if isinstance(base, dict) else base)
    status, draft = api(
        "POST", "/api/admin/notices/draft", admin,
        {
            "model_id": args.repo,
            "title": "Please declare the base model and its licence",
            "body": (
                "Hello! This card declares apache-2.0 and no base model. If the model derives from "
                f"{BASE}, declaring `base_model: {BASE}` and the upstream licence in the card metadata "
                "lets downstream users see the obligations that may apply. (This repo is ModelBrain's "
                "own test fixture; the notice is part of the hackathon demo.)"
            ),
        },
        args.api,
    )
    print("3. draft:", status, draft.get("id") if isinstance(draft, dict) else draft)
    status, posted = api("POST", f"/api/admin/notices/{draft['id']}/approve", admin, {}, args.api)
    print("   approve -> post:", status, {k: posted.get(k) for k in ("state", "posted_url")} if isinstance(posted, dict) else posted)
    print("4. author edits the card:", hf_commit(hf, args.repo, README_V2, "Declare base model and licence after the ModelBrain discussion"))
    time.sleep(3)
    status, after = api("POST", "/api/watch/check", admin, {"model_id": args.repo}, args.api)
    print("5. check now:", status, json.dumps({k: after.get(k) for k in ("changed", "changes")})[:400] if isinstance(after, dict) else after)
    status, closed = api("POST", "/api/admin/loop/close", admin, {"model_id": args.repo, "parent": BASE, "discussion_url": posted.get("posted_url") if isinstance(posted, dict) else None}, args.api)
    print("6. close the loop:", status, closed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
