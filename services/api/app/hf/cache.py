"""Disk cache for raw Hugging Face HTTP bodies. Never stores graph answers."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class DiskCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _file(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.root / digest[:2] / digest

    def get(self, key: str, *, max_age_s: float | None) -> bytes | None:
        path = self._file(key)
        meta = path.with_suffix(".meta")
        if not path.is_file() or not meta.is_file():
            return None
        info = json.loads(meta.read_text())
        age = time.time() - float(info["stored_at"])
        if max_age_s is not None and age > max_age_s:
            return None
        return path.read_bytes()

    def put(self, key: str, body: bytes) -> None:
        path = self._file(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.with_suffix(".meta").write_text(json.dumps({"stored_at": time.time(), "key": key}))
