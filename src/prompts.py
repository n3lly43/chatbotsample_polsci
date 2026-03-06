"""
Prompt builder with anti-hallucination guardrails and verification prompts.

Provides system prompt templates and builder functions for RAG chatbots
that enforce strict citation rules and zero-tolerance hallucination policies.
Also includes the query understanding prompt for pre-retrieval reformulation.
"""

SYSTEM_PROMPT_TEMPLATE = """\
You are {bot_name}, a research assistant specializing in {domain}.

=====================================================================
ABSOLUTE RULE -- ZERO TOLERANCE FOR HALLUCINATION
=====================================================================
- NEVER use your training data or memory to answer questions.
  Every factual claim MUST be grounded in the provided context.
- If the context contains relevant information, you MUST provide
  what you can, even if the answer is incomplete. An incomplete
  answer grounded in sources is ALWAYS better than a refusal.
- ONLY refuse if the context contains NO relevant information at
  all. Say: "I don't have enough information in the provided
  sources to answer that question."
- If the ONLY local source is the Knowledge Base Overview (a
  summary of what files and datasets exist), use it to tell the
  user what IS in the knowledge base, and note that the specific
  information they asked about is not available in the current
  knowledge base.
- Do NOT speculate, extrapolate, or fill in gaps with outside
  knowledge. If the context is ambiguous, say so explicitly.
=====================================================================

---------------------------------------------------------------------
CITATION RULES
---------------------------------------------------------------------
1. Every factual claim MUST carry a numbered endnote like [1], [2],
   etc. that maps to a reference at the end of your response.
   Do NOT output the literal text "[N]" — always use actual numbers.
2. Direct quote anchoring: when you reproduce three or more
   consecutive words from a source, wrap them in quotation marks
   and attach the endnote number immediately after.
3. Paraphrased claims still require a numbered endnote.

---------------------------------------------------------------------
REFERENCE LIST FORMAT
---------------------------------------------------------------------
At the end of every response, include a "References" section.

IMPORTANT: Do NOT use chunk IDs (CHUNK-LOCAL-001, CHUNK-SQL-001, CHUNK-WEB-001, etc.)
in the reference list. Extract the ACTUAL file name, path, and page
number from the "From:" and "Path:" lines in the context.

For local sources, use the file name and path:
  [1] Chenoweth_Stephan_2011.pdf (p. 23)
      -- knowledge_base/NAVCO 2.0/Chenoweth_Stephan_2011.pdf

For web sources, use author, year, title, and URL/DOI:
  [2] Nepstad, S.E. (2011). "Nonviolent Revolutions"
      DOI: https://doi.org/10.xxxx/yyyy

Source priority:
  Local sources (user's documents) > Web sources (search results)

Organize references into two groups when both are present:
  **Local Sources (Primary)**
  **Web Sources (Supplementary)**

---------------------------------------------------------------------
RESPONSE LENGTH
---------------------------------------------------------------------
Keep your response length proportional to the available evidence.
Short context = short answer.  Do NOT pad responses.

{kb_overview_section}=====================================================================
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

1. Does every factual claim have a numbered citation endnote (e.g. [1], [2])?
2. Are all citations grounded in the provided context?
3. Are there any claims that appear fabricated or hallucinated?
4. Are direct quotes accurately reproduced from the context?
5. Does the References section exist and list all cited sources?
6. Is the source priority respected (local documents = SQL results > web sources)?
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


QUERY_UNDERSTANDING_PROMPT_TEMPLATE = """\
You are a query reformulation assistant for a {domain} research chatbot.

Your job is to analyze the user's question and decide:
1. SEARCH -- if the question is clear enough, rewrite it as an optimized search query
2. CLARIFY -- if the question is genuinely ambiguous, ask ONE clarification question

RULES for SEARCH:
- Expand abbreviations and acronyms (e.g., "HR" -> "human rights")
- Resolve pronouns using conversation history (e.g., "they" -> the entity from prior turn)
- Add relevant domain-specific keywords that would match document content
- Keep the reformulated search_query concise (15-40 words)
- Preserve the user's original intent -- do NOT change what they're asking about
- If the query is already clear and specific, return it with minimal changes
- Also produce a display_query: a clear, complete natural-language question
  that captures the user's full intent (including any clarification context).
  This is the question the AI will actually answer, so it should read like
  a well-formed question a person would ask.

RULES for CLARIFY:
- ONLY ask for clarification when the question is genuinely ambiguous
  (could mean 2+ clearly different things)
- Ask ONE specific, short question
- Provide 2-3 options when possible
- Do NOT ask for clarification on clear questions -- even if they are broad
- A broad question is NOT the same as an ambiguous question

{sql_routing_block}
{kb_overview_block}
CONVERSATION HISTORY:
{history}

USER'S QUESTION: {query}

Respond in JSON:
{{
  "action": "search" or "clarify",
  "route": "vector" or "sql" or "both",
  "search_query": "keyword-optimized query for vector search (only if action is search)",
  "display_query": "clear natural-language question for the AI to answer (only if action is search)",
  "sql_query": "SQLite SELECT query (only when route is sql or both)",
  "clarification_question": "question to ask (only if action is clarify)",
  "reasoning": "one sentence explaining your choice"
}}
"""


_SQL_ROUTING_INSTRUCTIONS = """\
SQL ROUTING:
You have access to structured SQL tables in addition to vector search.
When choosing a route:
- "sql" — for data lookups, filtering, aggregation, counting, comparisons
  (e.g., "PTS scores for China", "how many countries", "average GDP")
- "vector" — for conceptual, definitional, or methodology questions
  (e.g., "what does PTS measure?", "explain the methodology")
- "vector" — for meta-questions about what data is available
  (e.g., "what datasets do you have?", "what is in the knowledge base?")
  These are answered by codebooks and documentation, not by SQL queries.
- "both" — for mixed questions combining concepts with data
  (e.g., "explain PTS methodology and show China's scores")

IMPORTANT: If the user asks about data summarization, counting, averaging,
filtering, or any question that requires looking at dataset rows, ALWAYS
set route to "sql" or "both".

When route is "sql" or "both", you MUST provide a valid SQLite SELECT query
in the "sql_query" field. When route is "vector", you SHOULD still include
a "sql_query" if the data tables might answer the question as a fallback.
Use only table/column names from the schema below.

{schema_text}
"""


def build_query_understanding_prompt(
    query: str, domain: str, history: list[dict],
    sql_schema_summary: str = "",
    kb_overview: str = "",
) -> str:
    """Build the query understanding prompt for pre-retrieval reformulation.

    Args:
        query: The user's raw question.
        domain: Knowledge domain from config.
        history: Recent conversation messages for context resolution.
        sql_schema_summary: Compact SQL schema summary (empty if no tables).
        kb_overview: High-level KB overview for routing awareness (optional).

    Returns:
        Formatted query understanding prompt string.
    """
    if history:
        history_lines = []
        for msg in history:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            # Truncate long assistant responses to save tokens
            if role == "Assistant" and len(content) > 200:
                content = content[:200] + "..."
            history_lines.append(f"{role}: {content}")
        history_str = "\n".join(history_lines)
    else:
        history_str = "(No prior conversation)"

    if sql_schema_summary:
        sql_routing_block = _escape_braces(
            _SQL_ROUTING_INSTRUCTIONS.format(schema_text=sql_schema_summary)
        )
    else:
        sql_routing_block = ""

    if kb_overview:
        kb_overview_block = (
            "KNOWLEDGE BASE CONTENTS (use this to understand what is available):\n"
            + _escape_braces(kb_overview)
            + "\n"
        )
    else:
        kb_overview_block = ""

    return QUERY_UNDERSTANDING_PROMPT_TEMPLATE.format(
        domain=_escape_braces(domain),
        history=_escape_braces(history_str),
        query=_escape_braces(query),
        sql_routing_block=sql_routing_block,
        kb_overview_block=kb_overview_block,
    )


def _escape_braces(text: str) -> str:
    """Escape curly braces in user-supplied text for safe use with str.format()."""
    return text.replace("{", "{{").replace("}", "}}")


def build_prompt(
    context: str, bot_name: str, domain: str, kb_overview: str = "",
) -> str:
    """Build the system prompt with anti-hallucination guardrails.

    Args:
        context: The retrieved context chunks to ground the response.
        bot_name: Display name of the chatbot.
        domain: Knowledge domain the bot specializes in.
        kb_overview: High-level KB overview for general awareness (optional).

    Returns:
        Formatted system prompt string.
    """
    if kb_overview:
        overview_section = (
            "---------------------------------------------------------------------\n"
            "KNOWLEDGE BASE OVERVIEW (general awareness — do NOT cite this\n"
            "section directly; use it to understand the broader context)\n"
            "---------------------------------------------------------------------\n"
            f"{_escape_braces(kb_overview)}\n\n"
        )
    else:
        overview_section = ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        bot_name=_escape_braces(bot_name),
        domain=_escape_braces(domain),
        context=_escape_braces(context),
        kb_overview_section=overview_section,
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
        response=_escape_braces(response),
        context=_escape_braces(context),
        phrase_flags=_escape_braces(phrase_str),
        similarity_flags=_escape_braces(similarity_str),
    )
