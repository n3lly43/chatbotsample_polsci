"""Anthropic LLM provider."""
SUPPORTED_MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-6"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 8192) -> str:
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
        error_msg = str(e)
        # Provide specific guidance based on error type
        if "auth" in error_type.lower() or "authentication" in error_type.lower():
            raise RuntimeError(f"Anthropic authentication failed. Check your API key.") from e
        elif "rate" in error_type.lower() or "429" in error_msg:
            raise RuntimeError(f"Anthropic rate limit exceeded. Wait a moment and try again.") from e
        elif "model" in error_msg.lower() or "not found" in error_msg.lower():
            raise RuntimeError(f"Anthropic model error: {error_msg}") from e
        else:
            raise RuntimeError(f"Anthropic API error ({error_type}): {error_msg}") from e

def list_models(api_key: str) -> list[str]:
    return list(SUPPORTED_MODELS)
