"""Anthropic LLM provider."""
SUPPORTED_MODELS = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    model = model or "claude-sonnet-4-6"
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        if not response.content:
            return ""
        return response.content[0].text or ""
    except Exception as e:
        error_type = type(e).__name__
        raise RuntimeError(f"Anthropic API error ({error_type}). Check your API key and network connection.") from e

def list_models(api_key: str) -> list[str]:
    return list(SUPPORTED_MODELS)
