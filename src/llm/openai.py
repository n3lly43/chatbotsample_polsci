"""OpenAI LLM provider."""
SUPPORTED_MODELS = ["gpt-5", "gpt-5-mini"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 8192) -> str:
    model = model or "gpt-5"
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    is_reasoning = model in ("o1", "o3", "o4", "o4-mini") or model.startswith(("o1-", "o3-", "o4-"))
    try:
        if is_reasoning:
            # Reasoning models include thinking tokens in max_completion_tokens,
            # so we need a larger budget to get enough output tokens.
            reasoning_budget = min(max(max_tokens * 4, 4096), 128000)
            messages = [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=reasoning_budget,
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
                max_tokens=max_tokens,
            )
        if not response.choices:
            return ""
        return response.choices[0].message.content or ""
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        # Provide specific guidance based on error type
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
