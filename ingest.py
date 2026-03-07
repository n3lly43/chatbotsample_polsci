"""Entry point for document ingestion."""

import sys

from src.ingest import ingest_documents
from src.config_loader import load_config


if __name__ == "__main__":
    try:
        cfg = load_config()
    except FileNotFoundError:
        print("Config file not found. Run 'python setup.py' first.")
        sys.exit(1)
    count = ingest_documents(cfg)
    if count == 0:
        print("\nNo documents were ingested. Add files to knowledge_base/ and try again.")
