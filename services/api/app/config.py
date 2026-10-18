"""Typed settings for every variable in `.env.example`."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("modelbrain.config")

ENV_KEYS: tuple[str, ...] = (
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "HF_TOKEN",
    "HF_WRITE_TOKEN",
    "HF_POST_ALLOWLIST",
    "OPENROUTER_API_KEY",
    "LLM_MODEL",
    "LLM_DAILY_BUDGET_CALLS",
    "EVAL_BASELINE_MODELS",
    "OPENROUTER_CATALOG_REFRESH_HOURS",
    "WEB_FETCHER",
    "FIRECRAWL_API_KEY",
    "ANAKIN_API_KEY",
    "ADMIN_TOKEN",
    "PUBLISHER_SALT",
    "CORS_ORIGINS",
    "WATCH_INTERVAL_MINUTES",
    "SANDBOX_TTL_MINUTES",
    "NEXT_PUBLIC_API_URL",
)

_LIST_KEYS = frozenset({"HF_POST_ALLOWLIST", "EVAL_BASELINE_MODELS", "CORS_ORIGINS"})

_settings: Settings | None = None


class ConfigError(RuntimeError):
    """Raised when a required setting is missing. Startup must stop."""


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    hf_token: str = ""
    hf_write_token: str = ""
    hf_post_allowlist: list[str] = Field(default_factory=list)
    openrouter_api_key: str = ""
    llm_model: str = ""
    llm_daily_budget_calls: int = 500
    eval_baseline_models: list[str] = Field(default_factory=list)
    openrouter_catalog_refresh_hours: int = 12
    web_fetcher: str = "httpx"
    firecrawl_api_key: str = ""
    anakin_api_key: str = ""
    admin_token: str
    publisher_salt: str
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3001"])
    watch_interval_minutes: int = 10
    sandbox_ttl_minutes: int = 120
    next_public_api_url: str = "http://localhost:8000"


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def load_settings(source: Mapping[str, str] | None = None) -> Settings:
    """Read settings. Blank HF_TOKEN warns. Blank admin token or salt fails."""
    env = os.environ if source is None else source
    missing = [
        key for key in ("ADMIN_TOKEN", "PUBLISHER_SALT") if not str(env.get(key, "")).strip()
    ]
    if missing:
        raise ConfigError(f"missing required setting: {', '.join(missing)}")

    raw: dict[str, object] = {}
    for key in ENV_KEYS:
        if key in ("ADMIN_TOKEN", "PUBLISHER_SALT"):
            raw[key.lower()] = str(env.get(key, "")).strip()
            continue
        value = env.get(key)
        if value is None or str(value).strip() == "":
            continue
        text = str(value).strip()
        raw[key.lower()] = _split_list(text) if key in _LIST_KEYS else text

    settings = Settings.model_validate(raw)
    if not settings.hf_token:
        log.warning("HF_TOKEN is not set; Hub calls will be anonymous")
    return settings


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings(os.environ)
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
