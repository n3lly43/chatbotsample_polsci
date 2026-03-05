"""Anthropic LLM provider."""
FALLBACK_MODELS = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = "claude-sonnet-4-6", temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    if not response.content:
        return ""
    return response.content[0].text or ""

def list_models(api_key: str) -> list[str]:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        models = client.models.list()
        return sorted([m.id for m in models.data])
    except Exception:
        return FALLBACK_MODELS
