"""Deterministic applies_when and check evaluation. The graph still supplies the clauses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import repo_root


def eu_countries() -> set[str]:
    payload = json.loads((repo_root() / "data" / "eu_countries.json").read_text())
    return set(payload["EU"])


def applies(rule: dict[str, Any] | None, scope: dict[str, Any], eu: set[str] | None = None) -> bool:
    if not rule:
        return False
    eu = eu_countries() if eu is None else eu
    if "always" in rule:
        return bool(rule["always"])
    if "hq_in" in rule:
        country = str(scope.get("hq_country") or "")
        target = rule["hq_in"]
        if target == "EU":
            return country in eu
        return country == target
    if "market_in" in rule:
        markets = [str(item) for item in scope.get("markets") or []]
        target = rule["market_in"]
        if target == "EU":
            return any(item in eu for item in markets)
        return target in markets
    if "commercial" in rule:
        return bool(scope.get("commercial")) is bool(rule["commercial"])
    if "mau_gt" in rule:
        return int(scope.get("mau") or 0) > int(rule["mau_gt"])
    if "distributes_weights" in rule:
        return bool(scope.get("distributes_weights")) is bool(rule["distributes_weights"])
    if "ancestor_multimodal" in rule:
        return bool(scope.get("ancestor_multimodal")) is bool(rule["ancestor_multimodal"])
    if "end_user_only" in rule:
        return bool(scope.get("end_user_only")) is bool(rule["end_user_only"])
    if "all" in rule:
        return all(applies(part, scope, eu) for part in rule["all"])
    if "any" in rule:
        return any(applies(part, scope, eu) for part in rule["any"])
    if "not" in rule:
        return not applies(rule["not"], scope, eu)
    return False


def obligation_status(check: dict[str, Any] | None, model: dict[str, Any]) -> str:
    """SATISFIED, NOT_SATISFIED, or NOT_CHECKABLE."""
    if not check:
        return "NOT_CHECKABLE"
    if "name_prefix" in check:
        prefix = str(check["name_prefix"])
        name = str(model.get("name_starts_with") or "")
        return "SATISFIED" if name == prefix or name.startswith(prefix) else "NOT_SATISFIED"
    if "card_mentions" in check:
        return "SATISFIED" if model.get("card_has_llama_notice") else "NOT_SATISFIED"
    if "license_file_present" in check:
        present = bool(model.get("has_license_file"))
        return "SATISFIED" if present is bool(check["license_file_present"]) else "NOT_SATISFIED"
    return "NOT_CHECKABLE"


def parse_json_field(value: Any) -> Any:
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def seed_path() -> Path:
    return repo_root() / "data" / "clauses.seed.json"
