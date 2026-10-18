"""G140: weight DNA sampler against synthetic safetensors served with Range semantics."""

from __future__ import annotations

import asyncio
import json
import re
import struct
from pathlib import Path

import httpx
import pytest

from app.hf.cache import DiskCache
from app.hf.client import HFClient
from app.hf.dna import (
    ERROR,
    GATED,
    OK,
    QUANTIZED,
    UNSUPPORTED_ARCH,
    Sampler,
    decode,
    target_tensors,
    window_start,
)

PER = 64  # small windows keep the synthetic files tiny


def _bf16(values: list[float]) -> bytes:
    out = b""
    for v in values:
        out += struct.pack("<I", struct.unpack("<I", struct.pack("<f", v))[0])[2:]
    return out


def _tensor_bytes(dtype: str, values: list[float]) -> bytes:
    if dtype == "BF16":
        return _bf16(values)
    if dtype == "F16":
        return struct.pack(f"<{len(values)}e", *values)
    if dtype == "F32":
        return struct.pack(f"<{len(values)}f", *values)
    return bytes(len(values))  # I8: one byte each


def build_safetensors(tensors: dict[str, tuple[str, list[int], list[float]]]) -> bytes:
    header: dict[str, object] = {"__metadata__": {"format": "pt"}}
    data = b""
    for name, (dtype, shape, values) in tensors.items():
        blob = _tensor_bytes(dtype, values)
        header[name] = {
            "dtype": dtype,
            "shape": shape,
            "data_offsets": [len(data), len(data) + len(blob)],
        }
        data += blob
    raw = json.dumps(header).encode()
    return struct.pack("<Q", len(raw)) + raw + data


def model_tensors(
    dtype: str = "BF16", layers: int = 4, hidden: int = 16, inter: int = 32, seed: float = 0.0
):
    tensors: dict[str, tuple[str, list[int], list[float]]] = {}
    for layer in range(layers):
        o = [((i * 7 + layer) % 13 - 6) / 8 + seed for i in range(hidden * hidden)]
        d = [((i * 5 + layer) % 11 - 5) / 8 + seed for i in range(hidden * inter)]
        tensors[f"model.layers.{layer}.self_attn.o_proj.weight"] = (dtype, [hidden, hidden], o)
        tensors[f"model.layers.{layer}.mlp.down_proj.weight"] = (dtype, [hidden, inter], d)
    return tensors


class Hub:
    """Serves /raw/ index files and /resolve/ weight files with HTTP Range support."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.status: dict[str, int] = {}
        self.ranges: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in self.status:
            return httpx.Response(self.status[path])
        body = self.files.get(path)
        if body is None:
            return httpx.Response(404)
        rng = request.headers.get("Range")
        if rng:
            self.ranges.append(rng)
            m = re.match(r"bytes=(\d+)-(\d+)", rng)
            assert m, rng
            start, end = int(m.group(1)), int(m.group(2))
            return httpx.Response(206, content=body[start : end + 1])
        return httpx.Response(200, content=body)


def _sampler(hub: Hub, tmp_path: Path) -> Sampler:
    client = HFClient(
        cache=DiskCache(tmp_path / "cache"), transport=httpx.MockTransport(hub.handler)
    )
    return Sampler(client, per_tensor=PER)


def run(coro):
    return asyncio.run(coro)


def test_window_start_is_32_aligned() -> None:
    assert window_start(1000) % 32 == 0
    assert window_start(2048 * 8192) == (int(2048 * 8192 * 0.37) // 32) * 32


def test_target_tensors_use_o_proj_and_down_proj() -> None:
    a, b = target_tensors("model.layers.", 16)
    assert a == "model.layers.4.self_attn.o_proj.weight"
    assert b == "model.layers.9.mlp.down_proj.weight"


def test_decode_bf16_round_trips() -> None:
    assert decode(_bf16([1.0, -2.5, 0.0]), "BF16") == [1.0, -2.5, 0.0]


@pytest.mark.parametrize("dtype", ["BF16", "F16", "F32"])
def test_single_file_fingerprint(dtype: str, tmp_path: Path) -> None:
    hub = Hub()
    hub.files["/acme/m/resolve/abc/model.safetensors"] = build_safetensors(model_tensors(dtype))
    result = run(_sampler(hub, tmp_path).fingerprint("acme/m", "abc"))
    assert result.status == OK, result.reason
    assert len(result.vector) == 2 * PER
    assert result.sig == "h16|L4|i32"
    assert hub.ranges[0] == "bytes=0-7"
    assert all(r.startswith("bytes=") for r in hub.ranges)


def test_sharded_fingerprint_reads_the_right_shard(tmp_path: Path) -> None:
    hub = Hub()
    tensors = model_tensors()
    first = {k: v for k, v in tensors.items() if ".layers.0." in k or ".layers.1." in k}
    second = {k: v for k, v in tensors.items() if k not in first}
    hub.files["/acme/s/resolve/abc/a.safetensors"] = build_safetensors(first)
    hub.files["/acme/s/resolve/abc/b.safetensors"] = build_safetensors(second)
    weight_map = {k: "a.safetensors" for k in first} | {k: "b.safetensors" for k in second}
    hub.files["/acme/s/raw/abc/model.safetensors.index.json"] = json.dumps(
        {"weight_map": weight_map}
    ).encode()
    single = run(_sampler(Hub(), tmp_path).fingerprint("x/y", "abc"))  # sanity: other repo missing
    assert single.status != OK
    result = run(_sampler(hub, tmp_path / "s").fingerprint("acme/s", "abc"))
    assert result.status == OK, result.reason
    assert result.tensors == [
        "model.layers.1.self_attn.o_proj.weight",
        "model.layers.2.mlp.down_proj.weight",
    ]


def test_same_weights_give_the_same_vector(tmp_path: Path) -> None:
    hub = Hub()
    hub.files["/a/one/resolve/s/model.safetensors"] = build_safetensors(model_tensors())
    hub.files["/b/two/resolve/s/model.safetensors"] = build_safetensors(model_tensors())
    sampler = _sampler(hub, tmp_path)
    one = run(sampler.fingerprint("a/one", "s"))
    two = run(sampler.fingerprint("b/two", "s"))
    assert one.vector == two.vector


def test_quantized_dtype(tmp_path: Path) -> None:
    hub = Hub()
    hub.files["/q/m/resolve/s/model.safetensors"] = build_safetensors(model_tensors("I8"))
    assert run(_sampler(hub, tmp_path).fingerprint("q/m", "s")).status == QUANTIZED


def test_missing_o_proj_is_unsupported(tmp_path: Path) -> None:
    hub = Hub()
    tensors = {k: v for k, v in model_tensors().items() if "o_proj" not in k}
    hub.files["/u/m/resolve/s/model.safetensors"] = build_safetensors(tensors)
    assert run(_sampler(hub, tmp_path).fingerprint("u/m", "s")).status == UNSUPPORTED_ARCH


def test_gated_repo(tmp_path: Path) -> None:
    hub = Hub()
    hub.status["/g/m/raw/s/model.safetensors.index.json"] = 401
    assert run(_sampler(hub, tmp_path).fingerprint("g/m", "s")).status == GATED


def test_truncated_header_is_error(tmp_path: Path) -> None:
    hub = Hub()
    full = build_safetensors(model_tensors())
    hub.files["/t/m/resolve/s/model.safetensors"] = full[:40]
    assert run(_sampler(hub, tmp_path).fingerprint("t/m", "s")).status == ERROR


def test_range_ignored_by_server_is_not_trusted(tmp_path: Path) -> None:
    body = build_safetensors(model_tensors())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("index.json"):
            return httpx.Response(404)
        return httpx.Response(200, content=body)  # ignores Range

    client = HFClient(cache=DiskCache(tmp_path / "c"), transport=httpx.MockTransport(handler))
    result = run(Sampler(client, per_tensor=PER).fingerprint("r/m", "s"))
    assert result.status == ERROR
