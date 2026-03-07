"""Google Gemini LLM provider (google-genai SDK)."""

SUPPORTED_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    from google import genai

    model = model or SUPPORTED_MODELS[0]
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        # Check for blocked responses
        if not response.text:
            return ""
        return response.text
    except ValueError as e:
        # Safety filter block — return empty so verifier treats it as generation failure
        return ""
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        if "auth" in error_type.lower() or "authentication" in error_type.lower() or "api_key" in error_msg.lower():
            raise RuntimeError(f"Gemini authentication failed. Check your API key.") from e
        elif "rate" in error_type.lower() or "429" in error_msg:
            raise RuntimeError(f"Gemini rate limit exceeded. Wait a moment and try again.") from e
        elif "model" in error_msg.lower() or "not found" in error_msg.lower():
            raise RuntimeError(f"Gemini model error: {error_msg}") from e
        else:
            raise RuntimeError(f"Gemini API error ({error_type}): {error_msg}") from e


def list_models(api_key: str) -> list[str]:
    return list(SUPPORTED_MODELS)
