"""Configuration and adapter setup for CVlizer."""

import os
from pathlib import Path
from dotenv import load_dotenv
from cognee.infrastructure.databases.vector import use_vector_adapter
from cognee_community_vector_adapter_qdrant import QDrantAdapter

# Load .env file from workspace root
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Register Qdrant vector adapter with Cognee
use_vector_adapter("qdrant", QDrantAdapter)

def get_config():
    """Returns basic app configuration dictionary."""
    return {
        "llm_provider": os.getenv("LLM_PROVIDER", "custom"),
        "llm_model": os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile"),
        "llm_api_key": os.getenv("LLM_API_KEY", ""),
        "vector_db_provider": os.getenv("VECTOR_DB_PROVIDER", "qdrant"),
        "vector_db_url": os.getenv("VECTOR_DB_URL", "http://localhost:6333"),
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "fastembed"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        "embedding_dimensions": int(os.getenv("EMBEDDING_DIMENSIONS", "384")),
    }
