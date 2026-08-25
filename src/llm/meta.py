
SUPPORTED_MODELS = ["meta-llama/Llama-3.3-70B-Instruct"]


def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = None, temperature: float = 0.0,
             max_tokens: int = 8192) -> str:
    from openai import OpenAI

    model = model or SUPPORTED_MODELS[0]
    client = OpenAI(base_url="https://router.huggingface.co/v1", 
                    api_key=api_key,
                    default_headers={"X-HF-Bill-To": "cgiar"})

    try:
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
        # Check for blocked responses
        if not response.choices:
            return ""
        return response.choices[0].message.content or ""
    except ValueError as e:
        # Safety filter block — return empty so verifier treats it as generation failure
        return ""
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        if "auth" in error_type.lower() or "authentication" in error_type.lower() or "api_key" in error_msg.lower():
            raise RuntimeError(f"Hugging Face authentication failed. Check your API key.") from e
        elif "rate" in error_type.lower() or "429" in error_msg:
            raise RuntimeError(f"Hugging Face rate limit exceeded. Wait a moment and try again.") from e
        elif "model" in error_msg.lower() or "not found" in error_msg.lower():
            raise RuntimeError(f"Hugging Face model error: {error_msg}") from e
        else:
            raise RuntimeError(f"Hugging Face API error ({error_type}): {error_msg}") from e


def list_models(api_key: str) -> list[str]:
    return list(SUPPORTED_MODELS)