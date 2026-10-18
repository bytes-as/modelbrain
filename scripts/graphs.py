"""Export and import FalkorDB graphs with DUMP / RESTORE (G111).

Seeds a fresh deployment from a local hub in seconds instead of re-crawling,
and keeps a restorable snapshot for judge day.

  python scripts/graphs.py export --host localhost --port 6379 --out exports
  python scripts/graphs.py import --host <host> --port <port> --in exports [--replace]

The password is read from FALKORDB_PASSWORD (never pass it on the command line).
Sandboxes (sbx_*) and test graphs are skipped: only hub and tenant_* are exported.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import redis

KEEP = ("hub", "tenant_")


def _client(host: str, port: int) -> redis.Redis:
    return redis.Redis(
        host=host, port=port, password=os.environ.get("FALKORDB_PASSWORD") or None, socket_timeout=60
    )


def export(host: str, port: int, out: Path) -> int:
    r = _client(host, port)
    names = sorted(
        n.decode() if isinstance(n, bytes) else str(n) for n in r.execute_command("GRAPH.LIST")
    )
    keep = [n for n in names if n == "hub" or n.startswith("tenant_")]
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in keep:
        blob = r.dump(name)
        if blob is None:
            continue
        (out / f"{name}.dump").write_bytes(blob)
        nodes = r.execute_command("GRAPH.RO_QUERY", name, "MATCH (n) RETURN count(n)")[1][0][0]
        manifest[name] = {"bytes": len(blob), "nodes": int(nodes)}
        print(f"exported {name}: {len(blob)} bytes, {nodes} nodes")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


def restore(host: str, port: int, src: Path, replace: bool) -> int:
    r = _client(host, port)
    manifest = json.loads((src / "manifest.json").read_text())
    for name, info in manifest.items():
        blob = (src / f"{name}.dump").read_bytes()
        args = ["RESTORE", name, 0, blob] + (["REPLACE"] if replace else [])
        try:
            r.execute_command(*args)
        except redis.ResponseError as exc:
            if "BUSYKEY" in str(exc):
                print(f"skip {name}: exists (use --replace)")
                continue
            raise
        nodes = r.execute_command("GRAPH.RO_QUERY", name, "MATCH (n) RETURN count(n)")[1][0][0]
        status = "ok" if int(nodes) == info["nodes"] else f"MISMATCH (expected {info['nodes']})"
        print(f"restored {name}: {nodes} nodes {status}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("--host", default=os.environ.get("FALKORDB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FALKORDB_PORT", "6379")))
    parser.add_argument("--out", type=Path, default=Path("exports"))
    parser.add_argument("--in", dest="src", type=Path, default=Path("exports"))
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.action == "export":
        return export(args.host, args.port, args.out)
    return restore(args.host, args.port, args.src, args.replace)


if __name__ == "__main__":
    sys.exit(main())
