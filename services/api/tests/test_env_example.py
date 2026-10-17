"""G017: .env.example lists exactly the variables app/config.py reads."""

from pathlib import Path

from app.config import ENV_KEYS


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env.example").is_file():
            return parent
    raise FileNotFoundError(".env.example")


def _example_keys() -> list[str]:
    keys: list[str] = []
    for line in (_repo_root() / ".env.example").read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.append(stripped.split("=", 1)[0].strip())
    return keys


def test_env_example_matches_config() -> None:
    assert _example_keys() == list(ENV_KEYS)
