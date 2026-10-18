"""G004: typed config, HF_TOKEN warning, required secrets."""

import logging

import pytest

from app.config import ENV_KEYS, ConfigError, load_settings


def _required(**extra: str) -> dict[str, str]:
    base = {"ADMIN_TOKEN": "admin-secret", "PUBLISHER_SALT": "salt-secret"}
    base.update(extra)
    return base


def test_defaults_and_types() -> None:
    settings = load_settings(
        _required(
            FALKORDB_PORT="6380",
            LLM_DAILY_BUDGET_CALLS="12",
            OPENROUTER_CATALOG_REFRESH_HOURS="6",
            WATCH_INTERVAL_MINUTES="15",
            SANDBOX_TTL_MINUTES="30",
            CORS_ORIGINS="http://localhost:3001, https://app.example",
            HF_POST_ALLOWLIST="acme/loop-test",
            HF_TOKEN="hf_test",
        )
    )
    assert settings.falkordb_host == "localhost"
    assert settings.falkordb_port == 6380
    assert settings.llm_daily_budget_calls == 12
    assert settings.openrouter_catalog_refresh_hours == 6
    assert settings.watch_interval_minutes == 15
    assert settings.sandbox_ttl_minutes == 30
    assert settings.web_fetcher == "httpx"
    assert settings.cors_origins == ["http://localhost:3001", "https://app.example"]
    assert settings.hf_post_allowlist == ["acme/loop-test"]
    assert settings.next_public_api_url == "http://localhost:8000"
    assert settings.admin_token == "admin-secret"
    assert settings.publisher_salt == "salt-secret"


def test_every_env_example_key_is_a_setting() -> None:
    field_names = {
        name.upper() for name in load_settings(_required(HF_TOKEN="x")).__class__.model_fields
    }
    assert field_names == set(ENV_KEYS)


def test_missing_hf_token_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="modelbrain.config"):
        settings = load_settings(_required())
    assert settings.hf_token == ""
    assert "HF_TOKEN" in caplog.text


def test_present_hf_token_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="modelbrain.config"):
        settings = load_settings(_required(HF_TOKEN="hf_live"))
    assert settings.hf_token == "hf_live"
    assert "HF_TOKEN" not in caplog.text


@pytest.mark.parametrize(
    "env",
    [
        {"PUBLISHER_SALT": "salt-secret"},
        {"ADMIN_TOKEN": "admin-secret"},
        {"ADMIN_TOKEN": "   ", "PUBLISHER_SALT": "salt-secret"},
        {"ADMIN_TOKEN": "admin-secret", "PUBLISHER_SALT": ""},
        {},
    ],
)
def test_missing_admin_token_or_salt_fails(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        load_settings(env)
