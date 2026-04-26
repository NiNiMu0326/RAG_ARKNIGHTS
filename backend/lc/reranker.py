"""
SiliconFlow Cross-Encoder Reranker as LangChain BaseDocumentCompressor.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import List, Optional, Sequence
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.callbacks.manager import Callbacks
from pydantic import Field
from backend import config
from backend.api.siliconflow import SiliconFlowClient


class SiliconFlowReranker(BaseDocumentCompressor):
    """SiliconFlow bge-reranker cross-encoder for document reranking."""

    api_key: str = Field(default="")
    model: str = Field(default="BAAI/bge-reranker-v2-m3")
    top_n: int = Field(default=5)

    class Config:
        arbitrary_types_allowed = True
        # 允许额外属性（如 _client）
        extra = "allow"

    def __init__(self, api_key: str = None, top_n: int = 5, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or config.SILICONFLOW_API_KEY
        self.top_n = top_n
        self._client = SiliconFlowClient(api_key=self.api_key)

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> List[Document]:
        """Rerank documents and return top_n with relevance_score in metadata."""
        if not documents:
            return []

        # 保存原始索引，便于后续去重
        doc_with_idx = []
        for i, doc in enumerate(documents):
            new_doc = Document(
                page_content=doc.page_content,
                metadata=dict(doc.metadata) if doc.metadata else {}
            )
            new_doc.metadata["original_index"] = i
            doc_with_idx.append(new_doc)

        doc_texts = [doc.page_content for doc in doc_with_idx]
        raw_results = self._client.rerank(query, doc_texts)

        # Sort by relevance_score descending
        raw_results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
        
        # 去重：基于 page_content 去重，保留第一个（最高分）的结果
        seen_content: set = set()
        reranked = []
        for r in raw_results:
            idx = r.get("index", 0)
            if idx < len(doc_with_idx):
                doc = doc_with_idx[idx]
                # 使用 chunk_id 或内容前100字符作为去重键
                chunk_id = doc.metadata.get("chunk_id", "")
                dedup_key = chunk_id if chunk_id else doc.page_content[:100]
                
                if dedup_key in seen_content:
                    continue
                seen_content.add(dedup_key)
                
                new_metadata = dict(doc.metadata)
                new_metadata["relevance_score"] = r.get("relevance_score", 0.0)
                reranked.append(
                    Document(
                        page_content=doc.page_content,
                        metadata=new_metadata,
                    )
                )
                if len(reranked) >= self.top_n:
                    break
        return reranked
