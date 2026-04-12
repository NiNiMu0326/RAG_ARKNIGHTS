"""
Backend LangChain Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

BASE_DIR = Path(__file__).parent.parent
CHUNKS_DIR = BASE_DIR / "chunks"
GRAPH_DIR = CHUNKS_DIR / "graphrag"
ENTITY_RELATIONS_FILE = GRAPH_DIR / "entity_relations.json"
EVAL_QUESTIONS_FILE = BASE_DIR / "eval" / "questions.json"
DATA_DIR = BASE_DIR / "data"

# API Keys
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY_2", "")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Model Settings
EMBEDDING_MODEL = "Pro/BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEEPSEEK_LLM_MODEL = "deepseek-chat"
LLM_MODEL = "Pro/Qwen/Qwen2.5-7B-Instruct"
DEFAULT_TEMPERATURE = 0.7

# CRAG Thresholds
CRAG_HIGH_THRESHOLD = 0.7
CRAG_LOW_THRESHOLD = 0.4

# Search Settings
RRF_K = 60
VECTOR_WEIGHT = 0.5

# FAISS
FAISS_INDEX_DIR = BASE_DIR / "faiss_index"
FAISS_INDEX_DIR_STR = str(FAISS_INDEX_DIR)


def get_bm25_index_path(collection_name: str) -> str:
    """Get the BM25 index pickle path for a given collection.

    Args:
        collection_name: One of 'operators', 'stories', 'knowledge'.
    """
    return str(CHUNKS_DIR / f"{collection_name}_bm25.pkl")

# LangSmith (activated via environment variables, no code needed):
# Set in .env:
#   LANGCHAIN_TRACING_V2=true
#   LANGCHAIN_API_KEY=your_key
#   LANGCHAIN_PROJECT=arknights-rag
