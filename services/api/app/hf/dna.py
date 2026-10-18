"""Weight DNA: sample a few weight values with HTTP Range reads (ADDENDUM_WEIGHT_DNA section 2).

Never downloads a weight file. Per model: one index lookup, a header read per
shard, and two 1 KB windows (o_proj at layer L*0.25, down_proj at layer L*0.6).
"""

from __future__ import annotations

import json
import logging
import math
import re
import struct
from dataclasses import dataclass, field
from typing import Any

from app.hf.client import HFClient

log = logging.getLogger("modelbrain.dna")

HUB = "https://huggingface.co"
PREFIXES = ("model.layers.", "language_model.model.layers.", "model.language_model.layers.")
MAX_HEADER = 25_000_000
REL_OFFSET = 0.37
DTYPE_SIZE = {"BF16": 2, "F16": 2, "F32": 4}

OK = "OK"
NO_SAFETENSORS = "NO_SAFETENSORS"
GATED = "GATED"
QUANTIZED = "QUANTIZED"
UNSUPPORTED_ARCH = "UNSUPPORTED_ARCH"
ERROR = "ERROR"


@dataclass
class DnaResult:
    status: str
    vector: list[float] = field(default_factory=list)
    sig: str = ""
    reason: str = ""
    tensors: list[str] = field(default_factory=list)


class DnaError(Exception):
    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def window_start(total_elements: int) -> int:
    """Start element of the sample window, aligned to 32 so Q8_0 blocks line up."""
    return (math.floor(total_elements * REL_OFFSET) // 32) * 32


def decode(raw: bytes, dtype: str) -> list[float]:
    if dtype == "BF16":
        count = len(raw) // 2
        halves = struct.unpack(f"<{count}H", raw[: count * 2])
        return list(
            struct.unpack(f"<{count}f", struct.pack(f"<{count}I", *(h << 16 for h in halves)))
        )
    if dtype == "F16":
        count = len(raw) // 2
        return list(struct.unpack(f"<{count}e", raw[: count * 2]))
    if dtype == "F32":
        count = len(raw) // 4
        return list(struct.unpack(f"<{count}f", raw[: count * 4]))
    raise DnaError(QUANTIZED, f"dtype {dtype} is not sampled")


def layer_prefix(keys: list[str] | set[str]) -> str:
    names = set(keys)
    for prefix in PREFIXES:
        if f"{prefix}0.self_attn.o_proj.weight" in names:
            return prefix
    raise DnaError(UNSUPPORTED_ARCH, "no o_proj tensor under a known layer prefix")


def layer_count(keys: list[str] | set[str], prefix: str) -> int:
    pattern = re.compile(re.escape(prefix) + r"(\d+)\.")
    found = [int(m.group(1)) for key in keys if (m := pattern.match(key))]
    if not found:
        raise DnaError(UNSUPPORTED_ARCH, "no numbered layers")
    return max(found) + 1


def target_tensors(prefix: str, layers: int) -> tuple[str, str]:
    a = math.floor(layers * 0.25)
    b = math.floor(layers * 0.6)
    return (f"{prefix}{a}.self_attn.o_proj.weight", f"{prefix}{b}.mlp.down_proj.weight")


def parse_header(raw: bytes) -> dict[str, Any]:
    try:
        header = json.loads(raw)
    except ValueError as exc:
        raise DnaError(ERROR, "header is not valid JSON") from exc
    if not isinstance(header, dict):
        raise DnaError(ERROR, "header is not an object")
    header.pop("__metadata__", None)
    return header


def validate_vector(vector: list[float], expected: int) -> None:
    if len(vector) != expected:
        raise DnaError(ERROR, f"vector length {len(vector)} != {expected}")
    if any(not math.isfinite(x) for x in vector):
        raise DnaError(ERROR, "vector contains NaN or Inf")
    if not any(vector):
        raise DnaError(ERROR, "vector is all zeros")


class Sampler:
    def __init__(self, client: HFClient, per_tensor: int = 512) -> None:
        self.client = client
        self.per_tensor = per_tensor
        self._headers: dict[str, tuple[int, dict[str, Any]]] = {}

    def _url(self, repo: str, sha: str, filename: str) -> str:
        return f"{HUB}/{repo}/resolve/{sha or 'main'}/{filename}"

    async def _weight_map(self, repo: str, sha: str) -> dict[str, str] | None:
        # /raw/ serves small non-LFS files directly; /resolve/ answers 307.
        response = await self.client.get(
            f"{HUB}/{repo}/raw/{sha or 'main'}/model.safetensors.index.json",
            cache_key=f"{repo}@{sha}:model.safetensors.index.json",
            ttl_s=None if sha and sha != "main" else 6 * 60 * 60,
        )
        if response.status in (401, 403):
            raise DnaError(GATED, "gated or private repo")
        if response.status != 200:
            return None
        try:
            data = response.json()
        except ValueError as exc:
            raise DnaError(ERROR, "index is not valid JSON") from exc
        weight_map = data.get("weight_map") if isinstance(data, dict) else None
        if not isinstance(weight_map, dict):
            raise DnaError(ERROR, "index has no weight_map")
        return {str(k): str(v) for k, v in weight_map.items()}

    async def _header(self, url: str) -> tuple[int, dict[str, Any]]:
        if url in self._headers:
            return self._headers[url]
        head = await self.client.get_range(url, 0, 7)
        if head.status in (401, 403):
            raise DnaError(GATED, "gated or private repo")
        if head.status == 404:
            raise DnaError(NO_SAFETENSORS, "no model.safetensors")
        if head.status != 206 or len(head.body) != 8:
            raise DnaError(ERROR, f"header length read returned {head.status}")
        (length,) = struct.unpack("<Q", head.body)
        if length <= 0 or length > MAX_HEADER:
            raise DnaError(ERROR, f"header length {length} out of range")
        body = await self.client.get_range(url, 8, 8 + length - 1)
        if body.status != 206 or len(body.body) != length:
            raise DnaError(ERROR, "truncated header")
        parsed = (length, parse_header(body.body))
        self._headers[url] = parsed
        return parsed

    async def _window(self, url: str, length: int, info: dict[str, Any]) -> list[float]:
        dtype = str(info.get("dtype"))
        size = DTYPE_SIZE.get(dtype)
        if size is None:
            raise DnaError(QUANTIZED, f"dtype {dtype} is not sampled")
        shape = info.get("shape") or []
        offsets = info.get("data_offsets") or []
        if len(offsets) != 2:
            raise DnaError(ERROR, "tensor has no data_offsets")
        total = math.prod(int(d) for d in shape) if shape else 0
        if total < self.per_tensor:
            raise DnaError(UNSUPPORTED_ARCH, "tensor smaller than the sample window")
        start = window_start(total)
        start = min(start, ((total - self.per_tensor) // 32) * 32)
        begin = 8 + length + int(offsets[0]) + start * size
        raw = await self.client.get_range(url, begin, begin + self.per_tensor * size - 1)
        if raw.status != 206 or len(raw.body) != self.per_tensor * size:
            raise DnaError(ERROR, f"window read returned {raw.status}")
        return decode(raw.body, dtype)

    async def fingerprint(self, repo: str, sha: str) -> DnaResult:
        try:
            weight_map = await self._weight_map(repo, sha)
            single = self._url(repo, sha, "model.safetensors")
            if weight_map is None:
                length, header = await self._header(single)
                keys: list[str] = list(header)
            else:
                keys = list(weight_map)
            prefix = layer_prefix(keys)
            layers = layer_count(keys, prefix)
            names = target_tensors(prefix, layers)
            vector: list[float] = []
            sig = ""
            for name in names:
                url = single if weight_map is None else self._url(repo, sha, weight_map[name])
                length, header = await self._header(url)
                info = header.get(name)
                if not isinstance(info, dict):
                    raise DnaError(UNSUPPORTED_ARCH, f"missing tensor {name}")
                if name.endswith("down_proj.weight"):
                    shape = info.get("shape") or []
                    if len(shape) != 2:
                        raise DnaError(UNSUPPORTED_ARCH, "down_proj is not 2-D")
                    sig = f"h{int(shape[0])}|L{layers}|i{int(shape[1])}"
                vector.extend(await self._window(url, length, info))
            validate_vector(vector, 2 * self.per_tensor)
            return DnaResult(OK, vector=vector, sig=sig, tensors=list(names))
        except DnaError as exc:
            log.info(
                "dna not sampled",
                extra={"repo": repo, "sha": sha, "status": exc.status, "reason": exc.reason},
            )
            return DnaResult(exc.status, reason=exc.reason)
