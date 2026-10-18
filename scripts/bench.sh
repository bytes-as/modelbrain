#!/usr/bin/env bash
# G048: p95 latency for a cached verdict (20 runs).
set -euo pipefail
API="${1:-http://localhost:8000}"
MODEL="${2:-OPEA/Llama-3.2V-11B-cot-int4-sym-inc}"
BODY=$(printf '{"model_id":"%s","context":{"hq_country":"DE","commercial":true}}' "$MODEL")

# Warm cache
curl -sS -o /dev/null -X POST "$API/api/verdict" -H 'Content-Type: application/json' -d "$BODY"

times=()
for _ in $(seq 1 20); do
  ms=$(
    python3 - <<PY
import time, urllib.request
body = b'''$BODY'''
req = urllib.request.Request("$API/api/verdict", data=body, headers={"Content-Type": "application/json"}, method="POST")
start = time.perf_counter()
with urllib.request.urlopen(req, timeout=30) as resp:
    resp.read()
print(int((time.perf_counter() - start) * 1000))
PY
  )
  times+=("$ms")
done

IFS=$'\n' sorted=($(printf '%s\n' "${times[@]}" | sort -n))
p95_index=$(( (${#sorted[@]} * 95 + 99) / 100 - 1 ))
p95="${sorted[$p95_index]}"
echo "runs=${times[*]}"
echo "p95_ms=$p95"
if [[ "$p95" -gt 1500 ]]; then
  echo "FAIL: p95 ${p95}ms exceeds 1500ms" >&2
  exit 1
fi
echo "PASS: p95 ${p95}ms <= 1500ms"
