"""
Backend Configuration
"""
import os
from pathlib import Path

def _load_env():
    """Load environment variables from .env file in backend directory."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

_load_env()

BASE_DIR = Path(__file__).parent.parent
CHUNKS_DIR = BASE_DIR / "chunks"
GRAPH_DIR = CHUNKS_DIR / "graphrag"
CHROMA_DIR = BASE_DIR / "chroma_db"
ENTITY_RELATIONS_FILE = GRAPH_DIR / "entity_relations.json"
EVAL_QUESTIONS_FILE = BASE_DIR / "eval" / "questions.json"
DATA_DIR = BASE_DIR / "data"

# API Keys - Load from environment variables
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY_2", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Model Settings (SiliconFlow - for embedding and reranking)
EMBEDDING_MODEL = "Pro/BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# Model Settings (DeepSeek - for chat/LLM)
DEEPSEEK_LLM_MODEL = "deepseek-coder-chat"
DEFAULT_TEMPERATURE = 0.7

# CRAG Thresholds
CRAG_HIGH_THRESHOLD = 0.7
CRAG_LOW_THRESHOLD = 0.4
CRAG_GRAY_ZONE = (0.35, 0.4)

# Search Settings
RRF_K = 60
VECTOR_WEIGHT = 0.5  # Vector search weight in hybrid search (0.5 = balanced)

# ChromaDB
CHROMA_PERSIST_DIR = str(CHROMA_DIR)
