"""G021 and G022: Hub payload parsing and licence normalisation."""

from __future__ import annotations

import json
from pathlib import Path

from app.hf.parse import load_normalise, normalise_license, parse_model


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "clauses.seed.json").is_file():
            return parent
    raise FileNotFoundError("data")


REPO = _repo()
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "hf"
SEED = json.loads((REPO / "data" / "clauses.seed.json").read_text())
TABLE = load_normalise(SEED)
ROOTS = {"meta-llama", "Qwen", "google"}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_normalise_known_list_other_and_missing() -> None:
    assert normalise_license("llama3.2", TABLE) == ("llama3.2", "llama3_2")
    assert normalise_license(["llama3.2", "apache-2.0"], TABLE)[1] == "llama3_2"
    assert normalise_license("made-up-licence", TABLE) == ("made-up-licence", "other")
    assert normalise_license(None, TABLE) == (None, "unknown")
    assert normalise_license("", TABLE) == (None, "unknown")


def test_six_recorded_models() -> None:
    opea = parse_model(
        "OPEA/Llama-3.2V-11B-cot-int4-sym-inc", _load("opea.json"), table=TABLE, roots=ROOTS
    )
    assert opea.license_key == "apache-2.0"
    assert opea.parents == [("Xkev/Llama-3.2V-11B-cot", "quantized")]
    assert opea.multimodal is False
    assert opea.is_root is False
    assert opea.name_starts_with == "Llama"

    xkev = parse_model(
        "Xkev/Llama-3.2V-11B-cot",
        _load("xkev.json"),
        table=TABLE,
        roots=ROOTS,
        readme="This model was Built with Llama.",
    )
    assert xkev.parents == [("meta-llama/Llama-3.2-11B-Vision-Instruct", "finetune")]
    assert xkev.card_has_llama_notice is True
    assert xkev.license_key == "apache-2.0"

    meta = parse_model(
        "meta-llama/Llama-3.2-11B-Vision-Instruct",
        _load("meta-vision.json"),
        table=TABLE,
        roots=ROOTS,
    )
    assert meta.is_root is True
    assert meta.license_key == "llama3_2"
    assert meta.multimodal is True
    assert meta.parents == []

    sicarius = parse_model(
        "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8",
        _load("sicarius.json"),
        table=TABLE,
        roots=ROOTS,
        config={"model_type": "llama", "hidden_size": 2048, "vocab_size": 128256},
    )
    assert sicarius.parents == []
    assert sicarius.is_root is False
    assert sicarius.license_key == "apache-2.0"
    assert any(item.kind == "config_fp" for item in sicarius.fingerprints)
    assert any(item.kind == "tokenizer_sha" for item in sicarius.fingerprints)

    nephilim = parse_model(
        "grimjim/llama-3-Nephilim-v1-8B", _load("nephilim.json"), table=TABLE, roots=ROOTS
    )
    assert len(nephilim.parents) >= 2
    assert {relation for _parent, relation in nephilim.parents} == {"merge"}

    qwen = parse_model("Qwen/Qwen2.5-7B-Instruct", _load("qwen.json"), table=TABLE, roots=ROOTS)
    assert qwen.license_key == "apache-2.0"
    assert qwen.multimodal is False
    assert qwen.has_license_file is True
    assert ("Qwen/Qwen2.5-7B", "finetune") in qwen.parents


def test_gated_skip_is_recorded() -> None:
    parsed = parse_model(
        "meta-llama/Llama-3.2-11B-Vision-Instruct",
        _load("meta-vision.json"),
        table=TABLE,
        roots=ROOTS,
        readme_skipped="README skipped: gated",
        config_skipped="config skipped: 401",
    )
    assert "README skipped: gated" in parsed.incomplete_reasons
    assert parsed.card_has_llama_notice is False
