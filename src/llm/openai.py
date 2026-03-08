"""OpenAI LLM provider."""
SUPPORTED_MODELS = ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]

# Models that don't support temperature or legacy max_tokens parameter.
# These require max_completion_tokens and the "developer" role instead of "system".
_RESTRICTED_PARAM_MODELS = {"gpt-5", "gpt-5-mini", "o1", "o3", "o4", "o4-mini"}
_RESTRICTED_PARAM_PREFIXES = ("o1-", "o3-", "o4-", "gpt-5-")


def _is_restricted_model(model: str) -> bool:
    """Check if the model restricts temperature/max_tokens/system role."""
    return model in _RESTRICTED_PARAM_MODELS or model.startswith(_RESTRICTED_PARAM_PREFIXES)


def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 8192) -> str:
    model = model or "gpt-4.1"
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    try:
        if _is_restricted_model(model):
            # These models don't support temperature or the "system" role.
            # Reasoning models need a larger budget for thinking tokens.
            is_reasoning = model in ("o1", "o3", "o4", "o4-mini") or model.startswith(("o1-", "o3-", "o4-"))
            budget = min(max(max_tokens * 4, 4096), 128000) if is_reasoning else max_tokens
            messages = [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=budget,
            )
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
        if not response.choices:
            return ""
        return response.choices[0].message.content or ""
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        if "auth" in error_type.lower() or "authentication" in error_type.lower():
            raise RuntimeError(f"OpenAI authentication failed. Check your API key.") from e
        elif "rate" in error_type.lower() or "429" in error_msg:
            raise RuntimeError(f"OpenAI rate limit exceeded. Wait a moment and try again.") from e
        elif "model" in error_msg.lower() or "not found" in error_msg.lower():
            raise RuntimeError(f"OpenAI model error: {error_msg}") from e
        else:
            raise RuntimeError(f"OpenAI API error ({error_type}): {error_msg}") from e

def list_models(api_key: str) -> list[str]:
    return list(SUPPORTED_MODELS)
