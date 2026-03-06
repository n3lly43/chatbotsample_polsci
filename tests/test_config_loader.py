import os
import pytest


def test_load_config_from_yaml(tmp_path):
    yaml_content = """
chatbot:
  name: "Test Bot"
  domain: "testing"
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 2048
api_keys:
  openai: ""
  anthropic: ""
  gemini: ""
embeddings:
  provider: "local"
  openai_model: "text-embedding-3-small"
retrieval:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 5
web_search:
  enabled: true
  backend: "semantic_scholar"
  max_results: 5
verification:
  enabled: true
  max_iterations: 3
  strict_mode: true
paths:
  knowledge_base: "knowledge_base"
  vector_db: "chroma_db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    from src.config_loader import load_config
    cfg = load_config(str(config_file))

    assert cfg["chatbot"]["name"] == "Test Bot"
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["model"] == "gpt-4o"
    assert cfg["retrieval"]["top_k"] == 5
    assert cfg["verification"]["enabled"] is True


def test_env_vars_override_api_keys(tmp_path):
    yaml_content = """
chatbot:
  name: "Test"
  domain: "test"
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 2048
api_keys:
  openai: "yaml-key"
  anthropic: ""
  gemini: ""
embeddings:
  provider: "local"
  openai_model: "text-embedding-3-small"
retrieval:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 5
web_search:
  enabled: false
  backend: "semantic_scholar"
  max_results: 5
verification:
  enabled: true
  max_iterations: 3
  strict_mode: true
paths:
  knowledge_base: "knowledge_base"
  vector_db: "chroma_db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    os.environ["OPENAI_API_KEY"] = "env-key"
    try:
        from src.config_loader import load_config
        cfg = load_config(str(config_file))
        assert cfg["api_keys"]["openai"] == "env-key"
    finally:
        del os.environ["OPENAI_API_KEY"]


def test_get_api_key_helper(tmp_path):
    yaml_content = """
chatbot:
  name: "Test"
  domain: "test"
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 2048
api_keys:
  openai: "test-key-123"
  anthropic: ""
  gemini: ""
embeddings:
  provider: "local"
  openai_model: "text-embedding-3-small"
retrieval:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 5
web_search:
  enabled: false
  backend: "semantic_scholar"
  max_results: 5
verification:
  enabled: true
  max_iterations: 3
  strict_mode: true
paths:
  knowledge_base: "knowledge_base"
  vector_db: "chroma_db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    from src.config_loader import load_config, get_api_key
    cfg = load_config(str(config_file))
    assert get_api_key(cfg, "openai") == "test-key-123"
    assert get_api_key(cfg, "anthropic") == ""
