"""Loads config.yaml and .env, exposes settings as a dict."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

_ENV_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"

    env_path = Path(config_path).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    if not Path(config_path).exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Run 'python setup.py' first to generate config.yaml and .env."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if not isinstance(cfg, dict):
        raise ValueError(
            f"Config file must contain a YAML mapping (dict), got {type(cfg).__name__}. "
            "Run 'python setup.py' to regenerate config.yaml."
        )

    # Normalize None-valued sections to empty dicts so chained .get() never
    # fails with AttributeError (e.g. `llm:` with no sub-keys → None).
    # Recurse into nested dicts so `paths:\n  vector_db:` also gets normalized.
    def _normalize_nulls(d):
        for key in list(d.keys()):
            if d[key] is None:
                d[key] = {}
            elif isinstance(d[key], dict):
                _normalize_nulls(d[key])
    _normalize_nulls(cfg)

    for provider, env_var in _ENV_KEY_MAP.items():
        env_val = os.environ.get(env_var)
        if env_val:
            cfg.setdefault("api_keys", {})[provider] = env_val

    return cfg


def get_api_key(cfg: dict, provider: str) -> str:
    env_var = _ENV_KEY_MAP.get(provider)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    return cfg.get("api_keys", {}).get(provider, "")
