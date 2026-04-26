"""
FAISS vector index wrapper for building and querying FAISS indexes.
Each collection (operators, stories, knowledge) has its own index file + metadata pkl.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pickle
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
            # Batch embed (batch size 20 to avoid API 413)
            batch_size = 20
            embeddings = []
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i + batch_size]
                texts = [d.page_content for d in batch_docs]
                batch_emb = embedding_fn.embed_documents(texts)
                embeddings.extend(batch_emb)

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
        meta = {}
        for i, doc in enumerate(documents):
            meta[i] = {
                "id": doc.metadata.get("chunk_id", f"doc_{i}"),
                "page_content": doc.page_content,
                "metadata": dict(doc.metadata),
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
