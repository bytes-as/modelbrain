#!/usr/bin/env bash
# G070-G072: smoke initialize / tools/list against /mcp
set -euo pipefail
API="${1:-http://localhost:8000}"
MCP="$API/mcp"

init=$(curl -sS -N -X POST "$MCP" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' | tr -d '\0' || true)
echo "$init" | head -c 400
echo

list=$(curl -sS -N -X POST "$MCP" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | tr -d '\0' || true)
echo "$list" | head -c 600
echo

if ! printf '%s\n%s\n' "$init" "$list" | grep -q 'can_i_use'; then
  echo "FAIL: can_i_use not listed" >&2
  exit 1
fi
if ! printf '%s\n' "$list" | grep -q 'explain'; then
  echo "FAIL: explain not listed" >&2
  exit 1
fi
if ! printf '%s\n' "$list" | grep -q 'lineage'; then
  echo "FAIL: lineage not listed" >&2
  exit 1
fi
echo "PASS: MCP tools include can_i_use, explain, lineage"