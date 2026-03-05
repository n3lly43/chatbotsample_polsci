"""Google Gemini LLM provider."""
FALLBACK_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = "gemini-2.5-flash", temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(
        model_name=model, system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens),
    )
    response = gen_model.generate_content(user_message)
    try:
        return response.text
    except ValueError:
        return ""

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
