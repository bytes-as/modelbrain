"""G148/G149: GGUF header parse and weight sampling against synthetic GGUF v3 files."""

from __future__ import annotations

import asyncio
import re
import struct
from pathlib import Path

import httpx

from app.engine.dna import cosine
from app.hf.cache import DiskCache
from app.hf.client import HFClient
from app.hf.dna import OK, QUANTIZED, Sampler
from app.hf.gguf import fingerprint_gguf, pick_file, vocab_hash
from tests.test_dna import PER, build_safetensors, model_tensors


def _s(text: str) -> bytes:
    raw = text.encode()
    return struct.pack("<Q", len(raw)) + raw


def _kv_str(key: str, value: str) -> bytes:
    return _s(key) + struct.pack("<I", 8) + _s(value)


def _kv_u32(key: str, value: int) -> bytes:
    return _s(key) + struct.pack("<I", 4) + struct.pack("<I", value)


def _kv_tokens(tokens: list[str]) -> bytes:
    body = b"".join(_s(t) for t in tokens)
    return (
        _s("tokenizer.ggml.tokens")
        + struct.pack("<I", 9)
        + struct.pack("<IQ", 8, len(tokens))
        + body
    )


def _q8(values: list[float]) -> bytes:
    out = b""
    for i in range(0, len(values), 32):
        block = values[i : i + 32]
        scale = max(abs(v) for v in block) / 127 or 1.0
        out += struct.pack("<e", scale) + struct.pack("<32b", *(round(v / scale) for v in block))
    return out


def build_gguf(
    kind: str = "F16", licence: str = "llama3.2", tokens: list[str] | None = None
) -> bytes:
    tensors = model_tensors("F32")
    names = [n for n in tensors]
    kv = [
        _kv_str("general.architecture", "llama"),
        _kv_str("general.license", licence),
        _kv_str("general.basename", "Synthetic"),
        _kv_u32("llama.block_count", 4),
        _kv_u32("llama.embedding_length", 16),
        _kv_u32("llama.feed_forward_length", 32),
        _kv_tokens(tokens or ["<s>", "a", "b"]),
    ]
    type_id = {"F16": 1, "Q8_0": 8, "Q4_K": 12}[kind]
    data = b""
    infos = b""
    for name in names:
        _dtype, shape, values = tensors[name]
        if kind == "F16":
            blob = struct.pack(f"<{len(values)}e", *values)
        elif kind == "Q8_0":
            blob = _q8(values)
        else:
            blob = bytes(len(values) // 2)
        layer = name.split(".")[2]
        gname = (
            f"blk.{layer}.attn_output.weight"
            if "o_proj" in name
            else f"blk.{layer}.ffn_down.weight"
        )
        dims = list(reversed(shape))
        infos += (
            _s(gname) + struct.pack("<I", len(dims)) + b"".join(struct.pack("<Q", d) for d in dims)
        )
        infos += struct.pack("<IQ", type_id, len(data))
        data += blob
        data += bytes((-len(data)) % 32)
    head = b"GGUF" + struct.pack("<IQQ", 3, len(names), len(kv)) + b"".join(kv) + infos
    head += bytes((-len(head)) % 32)
    return head + data


class Hub:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = self.files.get(request.url.path)
        if body is None:
            return httpx.Response(404)
        rng = request.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d+)-(\d+)", rng)
            start, end = int(m.group(1)), int(m.group(2))
            return httpx.Response(206, content=body[start : end + 1])
        return httpx.Response(200, content=body)


def _client(files: dict[str, bytes], tmp_path: Path) -> HFClient:
    return HFClient(
        cache=DiskCache(tmp_path / "c"), transport=httpx.MockTransport(Hub(files).handler)
    )


def test_gguf_f16_matches_its_safetensors_parent(tmp_path: Path) -> None:
    files = {
        "/p/base/resolve/s/model.safetensors": build_safetensors(model_tensors("F32")),
        "/g/quant/resolve/s/model-f16.gguf": build_gguf("F16"),
    }
    client = _client(files, tmp_path)
    parent = asyncio.run(Sampler(client, PER).fingerprint("p/base", "s"))
    child = asyncio.run(fingerprint_gguf(client, "g/quant", "s", "model-f16.gguf", PER))
    assert child.dna.status == OK, child.dna.reason
    assert child.dna.sig == parent.sig == "h16|L4|i32"
    assert cosine(child.dna.vector, parent.vector) > 0.9999
    assert child.license == "llama3.2" and child.basename == "Synthetic"


def test_gguf_q8_0_is_sampled_and_k_quants_are_reported(tmp_path: Path) -> None:
    files = {
        "/p/base/resolve/s/model.safetensors": build_safetensors(model_tensors("F32")),
        "/g/q8/resolve/s/m-Q8_0.gguf": build_gguf("Q8_0"),
        "/g/q4/resolve/s/m-Q4_K_M.gguf": build_gguf("Q4_K"),
    }
    client = _client(files, tmp_path)
    parent = asyncio.run(Sampler(client, PER).fingerprint("p/base", "s"))
    q8 = asyncio.run(fingerprint_gguf(client, "g/q8", "s", "m-Q8_0.gguf", PER))
    assert q8.dna.status == OK and cosine(q8.dna.vector, parent.vector) > 0.99
    q4 = asyncio.run(fingerprint_gguf(client, "g/q4", "s", "m-Q4_K_M.gguf", PER))
    assert q4.dna.status == QUANTIZED


def test_vocab_hash_is_format_independent_and_file_choice_prefers_samplable() -> None:
    tokens = ["<s>", "Ġthe", "é"]
    assert vocab_hash(tokens) == vocab_hash(list(tokens))
    assert vocab_hash(tokens) != vocab_hash(["<s>", "the", "é"])
    siblings = [
        {"rfilename": n} for n in ["m-Q4_K_M.gguf", "mmproj-f16.gguf", "m-Q8_0.gguf", "m-f16.gguf"]
    ]
    assert pick_file(siblings) == "m-f16.gguf"
    assert (
        pick_file([{"rfilename": "m-Q4_K_M.gguf"}, {"rfilename": "m-Q8_0.gguf"}]) == "m-Q8_0.gguf"
    )
    assert pick_file([{"rfilename": "README.md"}]) is None
