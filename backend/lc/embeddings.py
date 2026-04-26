"""
SiliconFlow Embeddings for LangChain.
Wraps the SiliconFlow bge-m3 API as a LangChain Embeddings class.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import List
from langchain_core.embeddings import Embeddings
from backend import config
from backend.api.siliconflow import SiliconFlowClient


class SiliconFlowEmbeddings(Embeddings):
    """SiliconFlow bge-m3 embeddings compatible with LangChain."""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or config.SILICONFLOW_API_KEY
        self.model = model or "Pro/BAAI/bge-m3"
        self._client = SiliconFlowClient(api_key=self.api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        if not texts:
            return []
        return self._client.embed(texts, model=self.model)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        result = self._client.embed([text], model=self.model)
        return result[0] if result else []
