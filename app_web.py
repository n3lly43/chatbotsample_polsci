"""Streamlit web UI for the RAG Research Chatbot."""

import streamlit as st

from src.config_loader import load_config, get_api_key
from src.ingest import get_chroma_collection, ingest_documents
from src.query_engine import understand_query
from src.retriever import retrieve
from src.verifier import verify_and_respond
from src.llm import list_models


# ── Session initialisation ───────────────────────────────────────────────────

def init_session():
    """Initialise st.session_state with messages list, cfg, and last_retrieval."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "cfg" not in st.session_state:
        try:
            st.session_state.cfg = load_config()
        except Exception as e:
            st.error(f"Configuration error: {e}\n\nPlease run `python setup.py` first.")
            st.stop()
    if "last_retrieval" not in st.session_state:
        st.session_state.last_retrieval = None
    if "pending_clarification" not in st.session_state:
        st.session_state.pending_clarification = None
    if "clarification_rounds" not in st.session_state:
        st.session_state.clarification_rounds = 0
    if "pending_clarification_question" not in st.session_state:
        st.session_state.pending_clarification_question = None


# ── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar():
    """Render sidebar with provider/model selectors, web search toggle, and KB stats."""
    cfg = st.session_state.cfg

    with st.sidebar:
        st.header("Settings")

        # --- Provider dropdown ---
        providers = ["openai", "anthropic", "gemini"]
        current_provider = cfg.get("llm", {}).get("provider", "openai")
        provider_index = providers.index(current_provider) if current_provider in providers else 0

        provider = st.selectbox(
            "LLM Provider",
            providers,
            index=provider_index,
            key="sidebar_provider",
        )

        # Update cfg in session when provider changes
        if provider != cfg.get("llm", {}).get("provider"):
            cfg.setdefault("llm", {})["provider"] = provider

        # --- Model dropdown (cached per provider) ---
        models_cache_key = f"models_{provider}"
        if models_cache_key not in st.session_state:
            api_key = get_api_key(cfg, provider)
            if api_key:
                try:
                    st.session_state[models_cache_key] = list_models(provider, api_key)
                except Exception:
                    st.session_state[models_cache_key] = []
            else:
                st.session_state[models_cache_key] = []

        available_models = st.session_state[models_cache_key]
        current_model = cfg.get("llm", {}).get("model", "")

        if available_models:
            model_index = (
                available_models.index(current_model)
                if current_model in available_models
                else 0
            )
            model = st.selectbox(
                "Model",
                available_models,
                index=model_index,
                key="sidebar_model",
            )
        else:
            model = st.text_input(
                "Model",
                value=current_model,
                key="sidebar_model_text",
            )

        # Update cfg in session when model changes
        if model != cfg.get("llm", {}).get("model"):
            cfg.setdefault("llm", {})["model"] = model

        # --- Web search toggle ---
        web_enabled = cfg.get("web_search", {}).get("enabled", False)
        web_toggle = st.toggle("Web search", value=web_enabled, key="sidebar_web_search")
        cfg.setdefault("web_search", {})["enabled"] = web_toggle

        st.divider()

        # --- Knowledge base stats ---
        st.subheader("Knowledge Base")
        try:
            collection = get_chroma_collection(cfg)
            chunk_count = collection.count()
            st.metric("Chunks indexed", chunk_count)
        except Exception as e:
            st.warning(f"Could not read knowledge base: {e}")
            chunk_count = 0

        # --- Re-ingest button ---
        if st.button("Re-ingest documents", use_container_width=True):
            with st.spinner("Ingesting documents..."):
                try:
                    count = ingest_documents(cfg)
                    st.success(f"Ingested {count} chunks.")
                    # Clear the cached chunk count so it refreshes
                    st.rerun()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")


# ── Chat interface ───────────────────────────────────────────────────────────

def render_chat():
    """Render the chat interface with message history and input."""
    cfg = st.session_state.cfg

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    prompt = st.chat_input("Ask a question about your knowledge base...")

    if prompt:
        # Show and store user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # ── Check if this is a clarification response ───────────────────
        pending = st.session_state.pending_clarification
        if pending is not None:
            # This prompt is the user's clarification answer
            # Include the clarification question for context
            pending_question = st.session_state.get("pending_clarification_question", "")
            if pending_question:
                combined = f"{pending} (Clarification: Q: {pending_question} A: {prompt})"
            else:
                combined = f"{pending} — {prompt}"
            st.session_state.pending_clarification_question = None
            original_query = pending
            st.session_state.pending_clarification = None
        else:
            combined = prompt
            original_query = prompt
            st.session_state.clarification_rounds = 0

        # ── Query understanding ─────────────────────────────────────────
        qu_cfg = cfg.get("query_understanding", {})
        qu_enabled = qu_cfg.get("enabled", True)
        max_history = qu_cfg.get("max_history", 6)

        search_query = combined
        display_query = combined
        route = "vector"
        sql_query = None
        max_clarifications = qu_cfg.get("max_clarifications", 1)

        if qu_enabled:
            # Exclude the just-appended user message to avoid sending
            # the current question twice (once in history, once as query)
            prior_messages = st.session_state.messages[:-1]
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in prior_messages[-max_history:]
            ]
            try:
                qu_result = understand_query(combined, cfg, history)
            except Exception:
                qu_result = {"action": "search", "search_query": combined, "display_query": combined, "original_query": original_query, "route": "vector", "sql_query": None}

            if qu_result.get("action") == "clarify" and st.session_state.clarification_rounds < max_clarifications:
                # Ask clarification — store original query and question for context
                st.session_state.pending_clarification = original_query
                st.session_state.pending_clarification_question = qu_result.get('clarification_question', 'Could you be more specific?')
                st.session_state.clarification_rounds += 1
                clarification_msg = f"**Before I search, could you clarify?** {qu_result.get('clarification_question', 'Could you be more specific?')}"
                st.session_state.messages.append(
                    {"role": "assistant", "content": clarification_msg}
                )
                with st.chat_message("assistant"):
                    st.markdown(clarification_msg)
                return

            # After max clarification rounds, force search (matches CLI behavior)
            if qu_result.get("action") == "clarify":
                qu_result["action"] = "search"

            search_query = qu_result.get("search_query", combined)
            display_query = qu_result.get("display_query", original_query)
            route = qu_result.get("route", "vector")
            sql_query = qu_result.get("sql_query")

        # Generate assistant response
        with st.chat_message("assistant"):
            with st.status("Searching knowledge base...", expanded=True) as status:
                # Show reformulated query if different
                if search_query != original_query:
                    status.update(label=f'Searching for: "{search_query}"...')

                # Retrieval
                try:
                    retrieval_result = retrieve(search_query, cfg, route=route, sql_query=sql_query)
                except Exception as e:
                    status.update(label=f"Retrieval error: {e}", state="error")
                    st.error(f"Retrieval failed: {e}")
                    return
                st.session_state.last_retrieval = retrieval_result

                n_local = len(retrieval_result.get("db_results", []))
                n_web = len(retrieval_result.get("web_results", []))
                n_sql = len(retrieval_result.get("sql_results", []))
                source_label = f"Found {n_local} local"
                if n_sql:
                    source_label += f" + {n_sql} SQL rows"
                source_label += f" + {n_web} web sources. Generating response..."
                status.update(label=source_label)

                # Response generation uses display_query — a clear,
                # complete question that incorporates any clarification context
                try:
                    result = verify_and_respond(display_query, retrieval_result, cfg)
                except Exception as e:
                    status.update(label=f"Generation error: {e}", state="error")
                    st.error(f"Response generation failed: {e}")
                    return

                # Update status based on verification outcome
                if result.get("refused"):
                    status.update(label="No sufficient sources found.", state="error")
                elif result.get("verification_passed") is True:
                    status.update(
                        label=f"Verified ({result.get('iterations', 0)} iteration(s)). "
                              f"{n_local} local + {n_web} web sources.",
                        state="complete",
                    )
                elif result.get("verification_passed") is False:
                    status.update(
                        label="Response generated (verification did not fully pass).",
                        state="error",
                    )
                else:
                    status.update(
                        label=f"Done. {n_local} local + {n_web} web sources.",
                        state="complete",
                    )

            # Display the response
            st.markdown(result.get("response", ""))

        # Store assistant message
        st.session_state.messages.append(
            {"role": "assistant", "content": result.get("response", "")}
        )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Orchestrate the Streamlit app."""
    st.set_page_config(
        page_title="ResearchBot",
        page_icon="🔬",
        layout="wide",
    )

    init_session()

    cfg = st.session_state.cfg
    bot_name = cfg.get("chatbot", {}).get("name", "ResearchBot")

    st.title(bot_name)

    render_sidebar()
    render_chat()

    st.caption(
        "All answers are sourced from the local knowledge base. "
        "Web sources are supplementary only. "
        "Every claim is citation-verified before display."
    )


if __name__ == "__main__":
    main()
