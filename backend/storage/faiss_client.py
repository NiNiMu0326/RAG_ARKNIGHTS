"""
FAISS vector index wrapper for building and querying FAISS indexes.
Each collection (operators, stories, knowledge) has its own index file + metadata pkl.
"""
import pickle
from pathlib import Path
import numpy as np
from typing import List, Dict, Optional, Tuple

from langchain_core.documents import Document
from backend import config


class FAISSClientWrapper:
    """Builds and loads FAISS indexes with associated document metadata."""

    def __init__(self, index_dir: str = None):
        self.index_dir = Path(index_dir) if index_dir else config.FAISS_INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self, collection_name: str) -> Path:
        return self.index_dir / f"{collection_name}.index"

    def _meta_path(self, collection_name: str) -> Path:
        return self.index_dir / f"{collection_name}_meta.pkl"

    @staticmethod
    def _embed_documents(
        documents: List[Document],
        embedding_fn,
        batch_size: int = 20,
    ) -> List[List[float]]:
        """Batch-embed documents (batch size 20 to avoid API 413)."""
        embeddings = []
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            texts = [d.page_content for d in batch_docs]
            embeddings.extend(embedding_fn.embed_documents(texts))
        return embeddings

    @staticmethod
    def _doc_to_meta_entry(doc: Document, internal_id: int) -> Dict:
        """Build a metadata entry for one document."""
        return {
            "id": doc.metadata.get("chunk_id", f"doc_{internal_id}"),
            "page_content": doc.page_content,
            "metadata": dict(doc.metadata),
        }

    def build_index(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: List[List[float]] = None,
        embedding_fn=None,
    ) -> None:
        """Build and save a FAISS index for the given collection.

        Args:
            collection_name: Name of the collection (operators, stories, knowledge)
            documents: List of LangChain Document objects
            embeddings: Pre-computed embeddings (optional)
            embedding_fn: Embedding function to use if embeddings not provided
        """
        if embeddings is None:
            if embedding_fn is None:
                raise ValueError("Either embeddings or embedding_fn must be provided")
            embeddings = self._embed_documents(documents, embedding_fn)

        import faiss
        dim = len(embeddings[0])
        vectors = np.array(embeddings, dtype=np.float32)

        # Normalize for cosine similarity (use IndexFlatIP on normalized vectors)
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)

        # Save index
        faiss.write_index(index, str(self._index_path(collection_name)))

        # Save metadata: id -> {page_content, metadata}
        meta = {
            i: self._doc_to_meta_entry(doc, i)
            for i, doc in enumerate(documents)
        }
        with open(self._meta_path(collection_name), "wb") as f:
            pickle.dump(meta, f)

    def load_index(self, collection_name: str) -> Optional[Tuple]:
        """Load a FAISS index and metadata.

        Returns:
            Tuple of (faiss_index, metadata_dict) or None if not found.
        """
        import faiss

        idx_path = self._index_path(collection_name)
        meta_path = self._meta_path(collection_name)

        if not idx_path.exists() or not meta_path.exists():
            return None

        index = faiss.read_index(str(idx_path))
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)

        return index, meta

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        embeddings: List[List[float]] = None,
        embedding_fn=None,
    ) -> int:
        """增量向已有 FAISS 索引追加文档。

        加载已有索引 → 嵌入新文档 → add 到 FAISS → 更新 metadata → 保存。
        返回追加后的总向量数。

        Args:
            collection_name: 集合名称
            documents: 新文档列表
            embeddings: 预计算的嵌入向量（可选）
            embedding_fn: 嵌入函数（embeddings 为空时必填）
        """
        import faiss

        # 生成新嵌入
        if embeddings is None:
            if embedding_fn is None:
                raise ValueError("Either embeddings or embedding_fn must be provided")
            embeddings = self._embed_documents(documents, embedding_fn)

        # 加载已有索引
        result = self.load_index(collection_name)
        if result is None:
            # 索引不存在，创建新的
            self.build_index(collection_name, documents, embeddings)
            return len(documents)

        index, meta = result
        old_count = index.ntotal

        # 归一化并追加向量
        vectors = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors)
        index.add(vectors)

        # 追加 metadata
        for i, doc in enumerate(documents):
            new_id = old_count + i
            meta[new_id] = self._doc_to_meta_entry(doc, new_id)

        # 保存
        faiss.write_index(index, str(self._index_path(collection_name)))
        with open(self._meta_path(collection_name), "wb") as f:
            pickle.dump(meta, f)

        return index.ntotal

    def get_chunk_count(self, collection_name: str) -> int:
        """Get number of vectors in the index."""
        import faiss

        idx_path = self._index_path(collection_name)
        if not idx_path.exists():
            return 0

        try:
            index = faiss.read_index(str(idx_path))
            return index.ntotal
        except Exception:
            return 0

    def to_langchain_faiss(
        self, collection_name: str, embedding_fn
    ):
        """Convert a saved FAISS index to a LangChain FAISS vector store.

        Args:
            collection_name: Collection to load
            embedding_fn: LangChain Embeddings instance (required by LangChain FAISS)

        Returns:
            langchain_community.vectorstores.FAISS instance or None
        """
        from langchain_community.vectorstores import FAISS
        from langchain_community.docstore.in_memory import InMemoryDocstore

        result = self.load_index(collection_name)
        if result is None:
            return None

        index, meta = result

        # Reconstruct LangChain Documents from metadata
        documents = []
        for idx in sorted(meta.keys()):
            m = meta[idx]
            doc = Document(
                page_content=m["page_content"],
                metadata=m["metadata"],
            )
            # Ensure chunk_id is always in metadata
            if "chunk_id" not in doc.metadata:
                doc.metadata["chunk_id"] = m["id"]
            documents.append(doc)

        if not documents:
            return None

        # Build LangChain FAISS from existing index + docstore (no re-embedding)
        docstore = InMemoryDocstore({i: doc for i, doc in enumerate(documents)})
        index_to_docstore_id = {i: i for i in range(len(documents))}
        return FAISS(
            embedding_function=embedding_fn,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_docstore_id,
        )
