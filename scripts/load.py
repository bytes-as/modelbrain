"""Load check (G104): N concurrent cached verdicts and weight-DNA reads; prints p50/p95 and errors.

  ADMIN_TOKEN=... python3 -I scripts/load.py --api http://localhost:8000 --n 50

The admin token exempts the run from per-IP rate limits (it measures the engine, not the limiter).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MODELS = [
    "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
    "Xkev/Llama-3.2V-11B-cot",
    "TroyDoesAI/Llama-3.1-8B-Instruct",
    "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8",
    "Qwen/Qwen2.5-7B-Instruct",
]


def _request(api: str, i: int) -> tuple[float, int]:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("ADMIN_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    model = MODELS[i % len(MODELS)]
    if i % 3 == 2:
        req = urllib.request.Request(f"{api}/api/dna/inherits/{model}", headers=headers)
    else:
        body = json.dumps(
            {"model_id": model, "context": {"hq_country": "DE" if i % 2 else "US"}}
        ).encode()
        req = urllib.request.Request(f"{api}/api/verdict", data=body, headers=headers, method="POST")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:
        status = 0
    return (time.perf_counter() - start) * 1000, status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()
    api = args.api.rstrip("/")
    for i in range(len(MODELS)):  # warm
        _request(api, i)
    with ThreadPoolExecutor(max_workers=args.n) as pool:
        results = list(pool.map(lambda i: _request(api, i), range(args.n)))
    times = sorted(ms for ms, _ in results)
    errors = [s for _, s in results if s != 200]
    p95 = times[max(0, int(len(times) * 0.95) - 1)]
    print(
        f"requests={len(times)} errors={len(errors)} p50={statistics.median(times):.0f}ms "
        f"p95={p95:.0f}ms max={times[-1]:.0f}ms"
    )
    return 0 if not errors and p95 < 2000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
