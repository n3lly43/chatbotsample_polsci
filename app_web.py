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
        st.session_state.cfg = load_config()
    if "last_retrieval" not in st.session_state:
        st.session_state.last_retrieval = None
    if "pending_clarification" not in st.session_state:
        st.session_state.pending_clarification = None


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
            combined = f"{pending} — {prompt}"
            original_query = pending
            st.session_state.pending_clarification = None
        else:
            combined = prompt
            original_query = prompt

        # ── Query understanding ─────────────────────────────────────────
        qu_cfg = cfg.get("query_understanding", {})
        qu_enabled = qu_cfg.get("enabled", True)
        max_history = qu_cfg.get("max_history", 6)

        search_query = combined
        response_query = combined  # query passed to verify_and_respond

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
                qu_result = {"action": "search", "search_query": combined, "original_query": combined}

            if qu_result["action"] == "clarify" and pending is None:
                # Ask clarification — store original query, show question
                st.session_state.pending_clarification = original_query
                clarification_msg = f"**Before I search, could you clarify?** {qu_result['clarification_question']}"
                st.session_state.messages.append(
                    {"role": "assistant", "content": clarification_msg}
                )
                with st.chat_message("assistant"):
                    st.markdown(clarification_msg)
                return

            search_query = qu_result.get("search_query", combined)

        # Generate assistant response
        with st.chat_message("assistant"):
            with st.status("Searching knowledge base...", expanded=True) as status:
                # Show reformulated query if different
                if search_query != response_query:
                    status.update(label=f'Searching for: "{search_query}"...')

                # Retrieval
                retrieval_result = retrieve(search_query, cfg)
                st.session_state.last_retrieval = retrieval_result

                n_local = len(retrieval_result.get("db_results", []))
                n_web = len(retrieval_result.get("web_results", []))
                status.update(
                    label=f"Found {n_local} local + {n_web} web sources. Generating response..."
                )

                # Verification and response generation (uses combined query
                # so the LLM answers the clarified question, not just the original)
                result = verify_and_respond(response_query, retrieval_result, cfg)

                # Update status based on verification outcome
                if result.get("refused"):
                    status.update(label="No sufficient sources found.", state="error")
                elif result.get("verification_passed") is True:
                    status.update(
                        label=f"Verified ({result['iterations']} iteration(s)). "
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
            st.markdown(result["response"])

        # Store assistant message
        st.session_state.messages.append(
            {"role": "assistant", "content": result["response"]}
        )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Orchestrate the Streamlit app."""
    init_session()

    cfg = st.session_state.cfg
    bot_name = cfg.get("chatbot", {}).get("name", "ResearchBot")

    st.set_page_config(
        page_title=bot_name,
        page_icon="🔬",
        layout="wide",
    )

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
