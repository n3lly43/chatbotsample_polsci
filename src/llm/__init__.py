"""LLM provider registry."""
from src.llm import openai as _openai
from src.llm import anthropic as _anthropic
from src.llm import gemini as _gemini
from src.config_loader import get_api_key

PROVIDERS = {
    "openai": _openai,
    "anthropic": _anthropic,
    "gemini": _gemini,
}

def generate(system_prompt: str, user_message: str, cfg: dict,
             provider: str = None, max_tokens: int = None) -> str:
    llm_cfg = cfg.get("llm", {})
    provider = provider or llm_cfg.get("provider", "openai")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")
    api_key = get_api_key(cfg, provider)
    if not api_key:
        raise ValueError(f"API key not set for {provider}. Set it in .env or config.yaml.")
    model = llm_cfg.get("model", "")
    temperature = llm_cfg.get("temperature", 0.0)
    if max_tokens is None:
        max_tokens = llm_cfg.get("max_tokens", 2048)
    return PROVIDERS[provider].generate(
        system_prompt=system_prompt, user_message=user_message,
        api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens,
    )

def list_models(provider: str, api_key: str) -> list[str]:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return PROVIDERS[provider].list_models(api_key)
