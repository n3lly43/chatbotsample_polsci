import pytest

def test_provider_registry_has_all_providers():
    from src.llm import PROVIDERS
    assert "openai" in PROVIDERS
    assert "anthropic" in PROVIDERS
    assert "gemini" in PROVIDERS

def test_generate_raises_on_unknown_provider():
    from src.llm import generate
    with pytest.raises(ValueError, match="Unknown provider"):
        generate("system", "user", provider="fake", cfg={"api_keys": {}})

def test_generate_raises_on_missing_api_key():
    from src.llm import generate
    cfg = {"api_keys": {"openai": ""}, "llm": {"provider": "openai", "model": "gpt-4o",
           "temperature": 0.0, "max_tokens": 100}}
    with pytest.raises(ValueError, match="API key"):
        generate("system", "user", provider="openai", cfg=cfg)

def test_list_models_fallback():
    from src.llm.openai import list_models
    models = list_models("invalid-key-123")
    assert isinstance(models, list)
    assert len(models) > 0
