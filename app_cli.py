"""Rich-powered CLI chatbot with slash commands and RAG pipeline."""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

from src.config_loader import load_config, get_api_key
from src.ingest import ingest_documents
from src.retriever import retrieve
from src.verifier import verify_and_respond
from src.llm import list_models

console = Console()

# ── Slash-command definitions ────────────────────────────────────────────────

HELP_TEXT = """\
Available commands:
  /help              Show this help message
  /sources           Show sources from the last response
  /ingest            Re-ingest documents from knowledge_base/
  /model             Switch LLM model interactively
  /websearch on|off  Toggle web search override for this session
  /quit /exit /q     Exit the chatbot
"""


def handle_command(user_input: str, cfg: dict, state: dict) -> str | None:
    """Handle slash commands.

    Returns:
        A string to display (help text, status message, etc.),
        or a sentinel string for special actions:
          - ``"__QUIT__"``   -- caller should exit
          - ``"__INGEST__"`` -- caller should run ingestion
          - ``"__MODEL__"``  -- caller should run model switch
        ``None`` if *user_input* is not a slash command (i.e. a regular query).
    """
    stripped = user_input.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit", "/q"):
        return "__QUIT__"

    if cmd == "/help":
        return HELP_TEXT

    if cmd == "/sources":
        last = state.get("last_retrieval")
        if last is None:
            return "No previous query. Ask a question first."
        return _format_sources(last)

    if cmd == "/ingest":
        return "__INGEST__"

    if cmd == "/model":
        return "__MODEL__"

    if cmd == "/websearch":
        if arg.lower() == "on":
            state["web_search_override"] = True
            return "Web search enabled for this session."
        elif arg.lower() == "off":
            state["web_search_override"] = False
            return "Web search disabled for this session."
        else:
            current = state.get("web_search_override")
            if current is None:
                status = "using config default"
            else:
                status = "on" if current else "off"
            return f"Usage: /websearch on|off  (currently: {status})"

    return f"Unknown command: {cmd}. Type /help for available commands."


# ── Source formatting ────────────────────────────────────────────────────────

def _format_sources(retrieval_result: dict) -> str:
    """Format sources from a retrieval result for display."""
    lines: list[str] = []

    db_results = retrieval_result.get("db_results", [])
    web_results = retrieval_result.get("web_results", [])

    if not db_results and not web_results:
        return "No sources were used for the last response."

    if db_results:
        lines.append("Local Sources:")
        for i, chunk in enumerate(db_results, 1):
            meta = chunk["metadata"]
            source = meta.get("source", "unknown")
            page = meta.get("page", "?")
            dataset = meta.get("dataset", "")
            dist = chunk.get("distance", None)
            dist_str = f"  (distance: {dist:.3f})" if dist is not None else ""
            lines.append(f"  [{i}] {source}, page {page} [{dataset}]{dist_str}")

    if web_results:
        if db_results:
            lines.append("")
        lines.append("Web Sources:")
        for i, r in enumerate(web_results, 1):
            year_str = f" ({r['year']})" if r.get("year") else ""
            lines.append(f"  [{i}] {r.get('authors', 'Unknown')}{year_str}. "
                         f"\"{r.get('title', 'Untitled')}\"")
            if r.get("url"):
                lines.append(f"      {r['url']}")

    return "\n".join(lines)


# ── Model switching ──────────────────────────────────────────────────────────

def _handle_model_switch(cfg: dict) -> None:
    """Interactively switch the LLM model."""
    provider = cfg.get("llm", {}).get("provider", "openai")
    current_model = cfg.get("llm", {}).get("model", "")

    console.print(f"\nCurrent provider: [bold]{provider}[/bold]")
    console.print(f"Current model:    [bold]{current_model}[/bold]\n")

    api_key = get_api_key(cfg, provider)
    if not api_key:
        console.print("[red]No API key set for this provider. Cannot list models.[/red]")
        return

    with console.status("Fetching available models..."):
        try:
            models = list_models(provider, api_key)
        except Exception as e:
            console.print(f"[red]Error fetching models: {e}[/red]")
            return

    if not models:
        console.print("[yellow]No models found.[/yellow]")
        return

    console.print("Available models:")
    for i, m in enumerate(models, 1):
        marker = " [bold green]<-- current[/bold green]" if m == current_model else ""
        console.print(f"  {i:3d}. {m}{marker}")

    console.print(f"\nEnter a number (1-{len(models)}) or press Enter to cancel:")
    try:
        choice = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\nCancelled.")
        return

    if not choice:
        console.print("Cancelled.")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            cfg["llm"]["model"] = models[idx]
            console.print(f"[green]Model switched to: {models[idx]}[/green]")
        else:
            console.print("[red]Invalid selection.[/red]")
    except ValueError:
        console.print("[red]Invalid input. Enter a number.[/red]")


# ── Main loop ────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the CLI chatbot main loop."""
    try:
        cfg = load_config()
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        console.print("Run the setup wizard first or create config.yaml manually.")
        sys.exit(1)

    bot_name = cfg.get("chatbot", {}).get("name", "ResearchBot")
    domain = cfg.get("chatbot", {}).get("domain", "research")

    # Welcome panel
    welcome = Text()
    welcome.append(f"{bot_name}", style="bold cyan")
    welcome.append(f" -- Your {domain} research assistant\n\n", style="dim")
    welcome.append(
        f"Hi! I'm your research assistant on {domain}. Ask me anything about "
        "the documents in your knowledge base — I'll search through them, "
        "cite my sources with numbered references, and verify every answer "
        "before showing it to you. If I can't find it in your documents, "
        "I'll let you know rather than guess.\n\n",
    )
    welcome.append("Type your question, or /help for commands.\n", style="italic")
    welcome.append("Type /quit to exit.", style="italic dim")
    console.print(Panel(welcome, title="Welcome", border_style="cyan"))

    # Session state
    state: dict = {
        "last_retrieval": None,
        "web_search_override": None,
    }

    while True:
        console.print()
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # ── Handle slash commands ────────────────────────────────────────
        result = handle_command(user_input, cfg, state)

        if result == "__QUIT__":
            console.print("[dim]Goodbye![/dim]")
            break

        if result == "__INGEST__":
            console.print()
            with console.status("Ingesting documents..."):
                try:
                    count = ingest_documents(cfg)
                    console.print(f"[green]Ingestion complete: {count} chunks.[/green]")
                except Exception as e:
                    console.print(f"[red]Ingestion error: {e}[/red]")
            continue

        if result == "__MODEL__":
            _handle_model_switch(cfg)
            continue

        if result is not None:
            # A display string (help text, sources, etc.)
            console.print(result)
            continue

        # ── RAG pipeline ─────────────────────────────────────────────────
        query = user_input

        # Apply web search override if set
        effective_cfg = cfg
        if state.get("web_search_override") is not None:
            # Shallow copy to avoid mutating config permanently
            effective_cfg = {**cfg}
            effective_cfg["web_search"] = {
                **cfg.get("web_search", {}),
                "enabled": state["web_search_override"],
            }

        # Retrieve
        with console.status("[bold blue]Searching knowledge base...[/bold blue]"):
            try:
                retrieval_result = retrieve(query, effective_cfg)
            except Exception as e:
                console.print(f"[red]Retrieval error: {e}[/red]")
                continue

        state["last_retrieval"] = retrieval_result

        # Generate + verify
        with console.status("[bold blue]Generating response...[/bold blue]"):
            try:
                result = verify_and_respond(query, retrieval_result, effective_cfg)
            except Exception as e:
                console.print(f"[red]Generation error: {e}[/red]")
                continue

        # ── Display response ─────────────────────────────────────────────
        response_text = result["response"]

        # Verification status line
        status_parts = []
        if result.get("refused"):
            status_parts.append("[red]Refused[/red]")
        elif result.get("verification_passed") is True:
            status_parts.append("[green]Verified[/green]")
        elif result.get("verification_passed") is False:
            status_parts.append("[yellow]Verification failed[/yellow]")
        else:
            status_parts.append("[dim]Verification skipped[/dim]")

        iterations = result.get("iterations", 0)
        if iterations > 0:
            status_parts.append(f"[dim]({iterations} iteration{'s' if iterations != 1 else ''})[/dim]")

        status_line = " ".join(status_parts)

        # Render with Rich
        console.print()
        console.print(Panel(
            Markdown(response_text),
            title=f"[bold]{bot_name}[/bold]",
            subtitle=status_line,
            border_style="blue",
            padding=(1, 2),
        ))

        # Source summary
        db_count = len(retrieval_result.get("db_results", []))
        web_count = len(retrieval_result.get("web_results", []))
        source_summary = f"[dim]Sources: {db_count} local"
        if web_count:
            source_summary += f", {web_count} web"
        source_summary += " -- type /sources for details[/dim]"
        console.print(source_summary)


if __name__ == "__main__":
    main()
