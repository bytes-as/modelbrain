"""GGUF DNA: read a GGUF header and sample weights with HTTP Range reads (ADDENDUM section 5).

GGUF is what people run in Ollama and LM Studio. The header carries the licence, base name,
shape and the full token list; the tensors carry the weights. We sample the same two windows
as for safetensors (attn_output at layer L*0.25, ffn_down at L*0.6), so a GGUF file lands in
the same FalkorDB vector index as its safetensors parent.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from typing import Any

from app.hf.client import HFClient
from app.hf.dna import (
    ERROR,
    OK,
    QUANTIZED,
    UNSUPPORTED_ARCH,
    DnaError,
    DnaResult,
    decode,
    validate_vector,
    window_start,
)

HUB = "https://huggingface.co"
CHUNK = 4 << 20
MAX_HEADER = 32 << 20
# ggml tensor types we can sample: F32, F16, Q8_0, BF16
F32, F16, Q8_0, BF16 = 0, 1, 8, 30
SCALARS = {
    0: ("B", 1),
    1: ("b", 1),
    2: ("H", 2),
    3: ("h", 2),
    4: ("I", 4),
    5: ("i", 4),
    6: ("f", 4),
    7: ("?", 1),
    10: ("Q", 8),
    11: ("q", 8),
    12: ("d", 8),
}
STRING, ARRAY = 8, 9
KEEP_KEYS = (
    "general.architecture",
    "general.license",
    "general.basename",
    "general.finetune",
    "general.name",
    "general.alignment",
)


def vocab_hash(tokens: list[str]) -> str:
    """Same function for tokenizer.json and GGUF: JSON-encoded tokens in id order, one per line."""
    digest = hashlib.sha256()
    for token in tokens:
        digest.update(json.dumps(token, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]


def pick_file(siblings: list[dict[str, Any]]) -> str | None:
    """Prefer a format we can sample: F16/BF16, then Q8_0, then anything else (reported QUANTIZED)."""
    names = [str(s.get("rfilename", "")) for s in siblings]
    ggufs = [n for n in names if n.lower().endswith(".gguf") and "mmproj" not in n.lower()]
    if not ggufs:
        return None

    def rank(name: str) -> tuple[int, str]:
        low = name.lower()
        if "bf16" in low or "f16" in low and "q" not in low.split("f16")[0][-3:]:
            return (0, name)
        if "q8_0" in low:
            return (1, name)
        return (2, name)

    return sorted(ggufs, key=rank)[0]


class _Reader:
    """Buffered reader over HTTP Range requests (the header holds the token list, often MBs)."""

    def __init__(self, client: HFClient, url: str) -> None:
        self.client, self.url = client, url
        self.buf = b""
        self.pos = 0

    async def need(self, n: int) -> None:
        while self.pos + n > len(self.buf):
            if len(self.buf) >= MAX_HEADER:
                raise DnaError(ERROR, "GGUF header larger than 32 MB")
            start = len(self.buf)
            got = await self.client.get_range(self.url, start, start + CHUNK - 1)
            if got.status in (401, 403):
                raise DnaError("GATED", "gated or private repo")
            if got.status != 206 or not got.body:
                raise DnaError(ERROR, f"GGUF range read returned {got.status}")
            self.buf += got.body

    async def read(self, n: int) -> bytes:
        await self.need(n)
        out = self.buf[self.pos : self.pos + n]
        self.pos += n
        return out

    async def unpack(self, fmt: str, size: int) -> Any:
        return struct.unpack("<" + fmt, await self.read(size))[0]

    async def string(self) -> str:
        length = await self.unpack("Q", 8)
        return (await self.read(length)).decode("utf-8", "replace")

    async def value(self, kind: int, *, keep: bool) -> Any:
        if kind == STRING:
            return await self.string()
        if kind == ARRAY:
            inner = await self.unpack("I", 4)
            count = await self.unpack("Q", 8)
            items = [await self.value(inner, keep=keep) for _ in range(count)]
            return items if keep else None
        fmt, size = SCALARS[kind]
        return await self.unpack(fmt, size)


@dataclass
class GgufHeader:
    meta: dict[str, Any] = field(default_factory=dict)
    tokens: list[str] = field(default_factory=list)
    tensors: dict[str, tuple[list[int], int, int]] = field(default_factory=dict)
    data_start: int = 0


async def read_header(client: HFClient, url: str) -> GgufHeader:
    reader = _Reader(client, url)
    if await reader.read(4) != b"GGUF":
        raise DnaError(ERROR, "not a GGUF file")
    version = await reader.unpack("I", 4)
    if version not in (2, 3):
        raise DnaError(UNSUPPORTED_ARCH, f"GGUF version {version}")
    n_tensors = await reader.unpack("Q", 8)
    n_kv = await reader.unpack("Q", 8)
    header = GgufHeader()
    for _ in range(n_kv):
        key = await reader.string()
        kind = await reader.unpack("I", 4)
        wanted = key in KEEP_KEYS or key.endswith(
            (".block_count", ".embedding_length", ".feed_forward_length")
        )
        is_tokens = key == "tokenizer.ggml.tokens"
        value = await reader.value(kind, keep=wanted or is_tokens)
        if is_tokens and isinstance(value, list):
            header.tokens = [str(t) for t in value]
        elif wanted:
            header.meta[key] = value
    for _ in range(n_tensors):
        name = await reader.string()
        n_dims = await reader.unpack("I", 4)
        dims = [await reader.unpack("Q", 8) for _ in range(n_dims)]
        ggml_type = await reader.unpack("I", 4)
        offset = await reader.unpack("Q", 8)
        header.tensors[name] = (dims, ggml_type, offset)
    align = int(header.meta.get("general.alignment") or 32)
    header.data_start = (reader.pos + align - 1) // align * align
    return header


def _q8_0(raw: bytes) -> list[float]:
    out: list[float] = []
    for i in range(0, len(raw) - 33, 34):
        (scale,) = struct.unpack("<e", raw[i : i + 2])
        out.extend(scale * q for q in struct.unpack("<32b", raw[i + 2 : i + 34]))
    return out


async def _window(
    client: HFClient, url: str, header: GgufHeader, name: str, per: int
) -> list[float]:
    if name not in header.tensors:
        raise DnaError(UNSUPPORTED_ARCH, f"missing tensor {name}")
    dims, kind, offset = header.tensors[name]
    total = math.prod(int(d) for d in dims)
    start = min(window_start(total), ((total - per) // 32) * 32)
    base = header.data_start + offset
    if kind in (F16, BF16, F32):
        size = 4 if kind == F32 else 2
        got = await client.get_range(url, base + start * size, base + (start + per) * size - 1)
        if got.status != 206:
            raise DnaError(ERROR, f"window read returned {got.status}")
        return decode(got.body, {F16: "F16", BF16: "BF16", F32: "F32"}[kind])
    if kind == Q8_0:
        first = base + (start // 32) * 34
        got = await client.get_range(url, first, first + (per // 32) * 34 - 1)
        if got.status != 206:
            raise DnaError(ERROR, f"window read returned {got.status}")
        return _q8_0(got.body)
    raise DnaError(QUANTIZED, f"ggml type {kind} is not sampled")


@dataclass
class GgufResult:
    dna: DnaResult
    file: str = ""
    license: str | None = None
    basename: str | None = None
    vocab: str | None = None


async def fingerprint_gguf(
    client: HFClient, repo: str, sha: str, filename: str, per: int = 512
) -> GgufResult:
    url = f"{HUB}/{repo}/resolve/{sha or 'main'}/{filename}"
    try:
        header = await read_header(client, url)
        arch = str(header.meta.get("general.architecture") or "")
        layers = int(header.meta.get(f"{arch}.block_count") or 0)
        hidden = int(header.meta.get(f"{arch}.embedding_length") or 0)
        inter = int(header.meta.get(f"{arch}.feed_forward_length") or 0)
        result = GgufResult(
            dna=DnaResult(ERROR),
            file=filename,
            license=(
                str(header.meta["general.license"]) if header.meta.get("general.license") else None
            ),
            basename=(
                str(header.meta["general.basename"])
                if header.meta.get("general.basename")
                else None
            ),
            vocab=vocab_hash(header.tokens) if header.tokens else None,
        )
        if not (layers and hidden and inter):
            raise DnaError(UNSUPPORTED_ARCH, "GGUF header lacks block_count/embedding/ffn length")
        a, b = math.floor(layers * 0.25), math.floor(layers * 0.6)
        names = [f"blk.{a}.attn_output.weight", f"blk.{b}.ffn_down.weight"]
        vector: list[float] = []
        for name in names:
            vector.extend(await _window(client, url, header, name, per))
        validate_vector(vector, 2 * per)
        result.dna = DnaResult(
            OK, vector=vector, sig=f"h{hidden}|L{layers}|i{inter}", tensors=names
        )
        return result
    except DnaError as exc:
        return GgufResult(dna=DnaResult(exc.status, reason=exc.reason), file=filename)
