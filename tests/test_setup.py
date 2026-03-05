import pytest

def test_generate_config_yaml():
    from setup import generate_config
    import yaml
    config_str = generate_config(
        bot_name="TestBot", domain="testing",
        provider="openai", model="gpt-4o", web_search=True,
    )
    cfg = yaml.safe_load(config_str)
    assert cfg["chatbot"]["name"] == "TestBot"
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["model"] == "gpt-4o"
    assert cfg["web_search"]["enabled"] is True
    assert cfg["verification"]["enabled"] is True
    assert cfg["paths"]["knowledge_base"] == "knowledge_base"
    # Ensure field names match what the rest of the codebase reads
    assert cfg["paths"]["vector_db"] == "chroma_db"
    assert cfg["web_search"]["backend"] == "semantic_scholar"
    assert cfg["verification"]["max_iterations"] == 3
    assert cfg["verification"]["strict_mode"] is True
    assert cfg["retrieval"]["chunk_size"] == 1000
    assert cfg["retrieval"]["chunk_overlap"] == 100
    assert cfg["retrieval"]["top_k"] == 50
    assert cfg["retrieval"]["max_distance"] == 0.55
    assert cfg["embeddings"]["provider"] == "local"
    # Query understanding config
    assert cfg["query_understanding"]["enabled"] is True
    assert cfg["query_understanding"]["max_history"] == 6
    assert cfg["query_understanding"]["max_clarifications"] == 1

def test_generate_env_file():
    from setup import generate_env
    env_str = generate_env("openai", "sk-test-123")
    assert "OPENAI_API_KEY=sk-test-123" in env_str
