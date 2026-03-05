"""
Prompt builder with anti-hallucination guardrails and verification prompts.

Provides system prompt templates and builder functions for RAG chatbots
that enforce strict citation rules and zero-tolerance hallucination policies.
"""

SYSTEM_PROMPT_TEMPLATE = """\
You are {bot_name}, a research assistant specializing in {domain}.

=====================================================================
ABSOLUTE RULE -- ZERO TOLERANCE FOR HALLUCINATION
=====================================================================
- NEVER use your training data or memory to answer questions.
  Every factual claim MUST be grounded in the provided context.
- If the answer is NOT in the context below, REFUSE to answer.
  Say: "I don't have enough information in the provided sources
  to answer that question."
- Do NOT speculate, extrapolate, or fill in gaps with outside
  knowledge. If the context is ambiguous, say so explicitly.
=====================================================================

---------------------------------------------------------------------
CITATION RULES
---------------------------------------------------------------------
1. Every factual claim MUST carry an endnote marker [N] that maps
   to a numbered reference at the end of your response.
2. Direct quote anchoring: when you reproduce three or more
   consecutive words from a source, wrap them in quotation marks
   and attach the endnote marker immediately after.
3. Paraphrased claims still require an endnote marker [N].

---------------------------------------------------------------------
REFERENCE LIST FORMAT
---------------------------------------------------------------------
At the end of every response, include a "References" section:

  **References**
  [1] <source title or chunk ID> -- <page / paragraph if available>
  [2] ...

Source priority:
  CHUNK-LOCAL (documents uploaded by the user) > CHUNK-WEB (web search results)

Organize references into two groups when both are present:
  **Local Sources (Primary)**
  **Web Sources (Supplementary)**

---------------------------------------------------------------------
RESPONSE LENGTH
---------------------------------------------------------------------
Keep your response length proportional to the available evidence.
Short context = short answer.  Do NOT pad responses.

=====================================================================
CONTEXT (use ONLY this to answer)
=====================================================================
{context}
=====================================================================
"""

VERIFICATION_PROMPT_TEMPLATE = """\
You are a verification agent. Your job is to audit the following
AI-generated response against the provided context and flag any
problems.

--- RESPONSE TO VERIFY ---
{response}
--- END RESPONSE ---

--- CONTEXT ---
{context}
--- END CONTEXT ---

--- PHRASE-LEVEL FLAGS ---
{phrase_flags}
--- END PHRASE FLAGS ---

--- SIMILARITY FLAGS ---
{similarity_flags}
--- END SIMILARITY FLAGS ---

Run through this 9-point verification checklist and report results:

1. Does every factual claim have a citation [N] endnote?
2. Are all citations grounded in the provided context?
3. Are there any claims that appear fabricated or hallucinated?
4. Are direct quotes accurately reproduced from the context?
5. Does the References section exist and list all cited sources?
6. Is the source priority respected (CHUNK-LOCAL > CHUNK-WEB)?
7. Are any phrase-level flags confirmed as hallucinations?
8. Do similarity flags indicate unsupported semantic drift?
9. Is the response length proportional to the available evidence?

Return your analysis as JSON in the following format:

{{
  "errors": [
    {{"check": 1, "description": "...", "severity": "high|medium|low"}}
  ],
  "error_count": 0,
  "pass": true,
  "summary": "Brief overall assessment"
}}

If there are no errors, return an empty "errors" list,
"error_count": 0, and "pass": true.
"""


def build_prompt(context: str, bot_name: str, domain: str) -> str:
    """Build the system prompt with anti-hallucination guardrails.

    Args:
        context: The retrieved context chunks to ground the response.
        bot_name: Display name of the chatbot.
        domain: Knowledge domain the bot specializes in.

    Returns:
        Formatted system prompt string.
    """
    return SYSTEM_PROMPT_TEMPLATE.format(
        bot_name=bot_name,
        domain=domain,
        context=context,
    )


def build_verification_prompt(
    response: str,
    context: str,
    phrase_flags: list[str],
    similarity_flags: list[str],
) -> str:
    """Build the verification prompt for auditing an AI response.

    Args:
        response: The AI-generated response to verify.
        context: The original context the response should be grounded in.
        phrase_flags: List of phrase-level flag descriptions.
        similarity_flags: List of similarity-based flag descriptions.

    Returns:
        Formatted verification prompt string.
    """
    phrase_str = (
        "\n".join(f"- {flag}" for flag in phrase_flags)
        if phrase_flags
        else "No phrase-level flags detected."
    )
    similarity_str = (
        "\n".join(f"- {flag}" for flag in similarity_flags)
        if similarity_flags
        else "No similarity flags detected."
    )
    return VERIFICATION_PROMPT_TEMPLATE.format(
        response=response,
        context=context,
        phrase_flags=phrase_str,
        similarity_flags=similarity_str,
    )
