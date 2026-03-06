"""Google Gemini LLM provider."""
FALLBACK_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    model = model or "gemini-2.5-flash"
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(
        model_name=model, system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens),
    )
    try:
        response = gen_model.generate_content(user_message)
        return response.text
    except ValueError:
        # Gemini raises ValueError when the response is blocked by safety filters.
        block_reason = getattr(response, "prompt_feedback", None)
        if block_reason:
            return f"[Gemini blocked: {block_reason}]"
        return "[Gemini blocked: response filtered by safety settings]"
    except Exception as e:
        return f"[Gemini error: {e}]"

def list_models(api_key: str) -> list[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        models = genai.list_models()
        chat_models = sorted([
            m.name.replace("models/", "") for m in models
            if "generateContent" in (m.supported_generation_methods or [])
        ])
        return chat_models if chat_models else FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS
