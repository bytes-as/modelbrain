"""Parse a Hugging Face model payload. Rules are FLOWS F2.3.2."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

CONFIG_KEYS = (
    "architectures",
    "model_type",
    "hidden_size",
    "intermediate_size",
    "num_hidden_layers",
    "num_attention_heads",
    "num_key_value_heads",
    "vocab_size",
    "max_position_embeddings",
    "rope_theta",
    "rope_scaling",
)

MULTIMODAL_PIPELINES = {
    "image-text-to-text",
    "visual-question-answering",
    "image-to-text",
    "any-to-any",
    "video-text-to-text",
}

RELATIONS = {"finetune", "adapter", "merge", "quantized"}


@dataclass
class Fingerprint:
    key: str
    kind: str
    value: str


@dataclass
class ParsedModel:
    model_id: str
    sha: str | None
    declared_license: str | None
    license_key: str
    pipeline_tag: str | None
    created_at: str | None
    last_modified: str | None
    gated: bool
    is_root: bool
    multimodal: bool
    card_has_llama_notice: bool
    has_license_file: bool
    name_starts_with: str
    parents: list[tuple[str, str]] = field(default_factory=list)
    fingerprints: list[Fingerprint] = field(default_factory=list)
    incomplete_reasons: list[str] = field(default_factory=list)


def load_normalise(seed: dict[str, Any]) -> dict[str, str]:
    table = seed.get("normalise", {})
    return {
        str(key).lower(): str(value) for key, value in table.items() if not str(key).startswith("_")
    }


def normalise_license(raw: object, table: dict[str, str]) -> tuple[str | None, str]:
    """Return (raw declared string or None, normalised key)."""
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None or str(raw).strip() == "":
        return None, "unknown"
    text = str(raw).strip()
    return text, table.get(text.lower(), "other")


def name_starts_with(model_id: str) -> str:
    repo = model_id.split("/", 1)[-1]
    token = re.split(r"[-_.]", repo, maxsplit=1)[0]
    return token


def parse_parents(card: dict[str, Any], tags: list[str]) -> list[tuple[str, str]]:
    parents: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(parent_id: str, relation: str) -> None:
        parent_id = parent_id.strip()
        if not parent_id or parent_id in seen:
            return
        if relation not in RELATIONS:
            relation = "finetune"
        seen.add(parent_id)
        parents.append((parent_id, relation))

    for tag in tags:
        if not tag.startswith("base_model:"):
            continue
        _prefix, relation, parent_id = (tag.split(":", 2) + ["", ""])[:3]
        if parent_id:
            add(parent_id, relation)

    base = card.get("base_model")
    if isinstance(base, str):
        add(base, "finetune")
    elif isinstance(base, list) and base:
        relation = "merge" if len(base) > 1 else "finetune"
        for item in base:
            if isinstance(item, str):
                add(item, relation)
    return parents


def declared_license_raw(card: dict[str, Any], tags: list[str]) -> object:
    if "license" in card and card.get("license") not in (None, ""):
        return card.get("license")
    for tag in tags:
        if tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return None


def is_multimodal(pipeline_tag: str | None, tags: list[str]) -> bool:
    if pipeline_tag in MULTIMODAL_PIPELINES:
        return True
    lowered = {tag.lower() for tag in tags}
    return "multimodal" in lowered or "vision" in lowered


def has_license_file(siblings: list[dict[str, Any]]) -> bool:
    for sibling in siblings:
        name = str(sibling.get("rfilename", "")).upper()
        if "LICENSE" in name or "LICENCE" in name:
            return True
    return False


def card_has_llama_notice(readme: str | None) -> bool:
    if not readme:
        return False
    return "built with llama" in readme.lower()


def fingerprints_from(
    siblings: list[dict[str, Any]], config: dict[str, Any] | None
) -> list[Fingerprint]:
    found: list[Fingerprint] = []
    tokenizer: Fingerprint | None = None
    tokenizer_fallback: Fingerprint | None = None
    for sibling in siblings:
        name = str(sibling.get("rfilename", ""))
        lfs = sibling.get("lfs") or {}
        sha = lfs.get("sha256") if isinstance(lfs, dict) else None
        blob = sibling.get("blobId")
        if name.endswith(".safetensors") or name.endswith(".bin"):
            if sha:
                found.append(
                    Fingerprint(key=f"weights_sha256:{sha}", kind="weights_sha256", value=str(sha))
                )
            continue
        if name == "tokenizer.json" and (sha or blob):
            value = str(sha or blob)
            tokenizer = Fingerprint(key=f"tokenizer_sha:{value}", kind="tokenizer_sha", value=value)
        elif name == "tokenizer.model" and (sha or blob):
            value = str(sha or blob)
            tokenizer_fallback = Fingerprint(
                key=f"tokenizer_sha:{value}", kind="tokenizer_sha", value=value
            )
    if tokenizer:
        found.append(tokenizer)
    elif tokenizer_fallback:
        found.append(tokenizer_fallback)
    if config:
        picked = {key: config[key] for key in CONFIG_KEYS if key in config}
        if picked:
            canonical = json.dumps(
                picked, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            found.append(Fingerprint(key=f"config_fp:{digest}", kind="config_fp", value=digest))
    return found


def parse_model(
    model_id: str,
    payload: dict[str, Any],
    *,
    table: dict[str, str],
    roots: set[str],
    readme: str | None = None,
    config: dict[str, Any] | None = None,
    readme_skipped: str | None = None,
    config_skipped: str | None = None,
) -> ParsedModel:
    card = payload.get("cardData") or {}
    if not isinstance(card, dict):
        card = {}
    tags = [str(tag) for tag in payload.get("tags") or []]
    siblings = [item for item in payload.get("siblings") or [] if isinstance(item, dict)]
    raw, key = normalise_license(declared_license_raw(card, tags), table)
    parents = parse_parents(card, tags)
    owner = model_id.split("/", 1)[0]
    reasons: list[str] = []
    if readme_skipped:
        reasons.append(readme_skipped)
    if config_skipped:
        reasons.append(config_skipped)
    gated = payload.get("gated")
    return ParsedModel(
        model_id=model_id,
        sha=payload.get("sha"),
        declared_license=raw,
        license_key=key,
        pipeline_tag=payload.get("pipeline_tag"),
        created_at=payload.get("createdAt"),
        last_modified=payload.get("lastModified"),
        gated=bool(gated) and gated is not False,
        is_root=owner in roots and not parents,
        multimodal=is_multimodal(payload.get("pipeline_tag"), tags),
        card_has_llama_notice=card_has_llama_notice(readme),
        has_license_file=has_license_file(siblings),
        name_starts_with=name_starts_with(model_id),
        parents=parents,
        fingerprints=fingerprints_from(siblings, config),
        incomplete_reasons=reasons,
    )
