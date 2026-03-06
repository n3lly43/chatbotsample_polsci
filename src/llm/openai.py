"""OpenAI LLM provider."""
SUPPORTED_MODELS = ["gpt-4.1", "gpt-4o", "gpt-4o-mini"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    model = model or "gpt-4o"
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    is_reasoning = model.startswith(("o1", "o3", "o4"))
    try:
        if is_reasoning:
            # Reasoning models include thinking tokens in max_completion_tokens,
            # so we need a larger budget to get enough output tokens.
            reasoning_budget = max(max_tokens * 4, 4096)
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
        raise RuntimeError(f"OpenAI API error ({error_type}). Check your API key and network connection.") from e

def list_models(api_key: str) -> list[str]:
    return list(SUPPORTED_MODELS)
