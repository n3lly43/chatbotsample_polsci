"""OpenAI LLM provider."""
FALLBACK_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    model = model or "gpt-4o"
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    is_reasoning = model.startswith(("o1", "o3", "o4"))
    if is_reasoning:
        messages = [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,
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

def list_models(api_key: str) -> list[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        chat_models = sorted([m.id for m in models if "gpt" in m.id or m.id.startswith(("o1", "o3", "o4"))])
        return chat_models if chat_models else FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS
