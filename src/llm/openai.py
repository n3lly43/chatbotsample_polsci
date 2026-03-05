"""OpenAI LLM provider."""
FALLBACK_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = "gpt-4o", temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model, temperature=temperature, max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    if not response.choices:
        return ""
    return response.choices[0].message.content or ""

def list_models(api_key: str) -> list[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        chat_models = sorted([m.id for m in models if "gpt" in m.id or m.id.startswith("o")])
        return chat_models if chat_models else FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS
