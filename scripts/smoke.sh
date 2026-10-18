#!/usr/bin/env bash
# Smoke test a ModelBrain deployment (G016).
# Usage: scripts/smoke.sh <api-base> [web-base]
#   scripts/smoke.sh http://localhost:8000 http://localhost:3001
set -euo pipefail

API="${1:?usage: scripts/smoke.sh <api-base> [web-base]}"
WEB="${2:-}"
FAIL=0

check() {
  local name="$1" cond="$2"
  if [ "$cond" = "1" ]; then echo "ok   $name"; else echo "FAIL $name"; FAIL=1; fi
}

json() { python3 -I -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

health=$(curl -fsS -m 10 "$API/api/health")
check "health: falkordb up" "$(echo "$health" | json "int(d.get('falkordb')=='up')")"

verdict() {
  curl -fsS -m 60 -X POST "$API/api/verdict" -H 'content-type: application/json' \
    -d "{\"model_id\":\"OPEA/Llama-3.2V-11B-cot-int4-sym-inc\",\"context\":{\"hq_country\":\"$1\",\"markets\":[\"$1\"],\"commercial\":true,\"mau\":1000,\"distributes_weights\":false,\"end_user_only\":false}}"
}
check "OPEA in DE is BLOCKED" "$(verdict DE | json "int(d.get('verdict')=='BLOCKED')")"
check "OPEA in US is not BLOCKED" "$(verdict US | json "int(d.get('verdict') in ('ALLOWED','ALLOWED_WITH_OBLIGATIONS'))")"

lineage=$(curl -fsS -m 30 "$API/api/models/OPEA/Llama-3.2V-11B-cot-int4-sym-inc/lineage")
check "lineage reaches Meta" "$(echo "$lineage" | python3 -I -c "import sys; print(int('meta-llama/Llama-3.2-11B-Vision-Instruct' in sys.stdin.read()))")"

replay=$(curl -fsS -m 30 "$API/api/replay/xkev")
check "Xkev replay has 9 descendants" "$(echo "$replay" | json "int(len(d.get('graph_descendants',[]))>=9)")"

coverage=$(curl -fsS -m 30 "$API/api/dna/coverage")
check "weight DNA fingerprints present" "$(echo "$coverage" | json "int(d.get('by_status',{}).get('OK',0)>0)")"

tools=$(curl -fsS -m 30 -X POST "$API/mcp" -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}')
check "MCP lists can_i_use" "$(echo "$tools" | grep -q '"can_i_use"' && echo 1 || echo 0)"
check "MCP lists trace_weights" "$(echo "$tools" | grep -q '"trace_weights"' && echo 1 || echo 0)"

if [ -n "$WEB" ]; then
  for page in / /findings /replay/xkev /hidden-lineage /companies; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 30 "$WEB$page")
    check "web $page returns 200" "$([ "$code" = "200" ] && echo 1 || echo 0)"
  done
fi

exit $FAIL
