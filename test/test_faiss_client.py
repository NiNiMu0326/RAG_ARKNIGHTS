"""
Tests for backend.storage.faiss_client: FAISSClientWrapper.
Usage: cd test && python -m pytest test_faiss_client.py -v
"""
import sys
import json
import pickle
import tempfile
import numpy as np
import pytest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.storage.faiss_client import FAISSClientWrapper


# ============================================================
# Helper: create a minimal LangChain-like Document
# ============================================================

class FakeDocument:
    """Minimal LangChain Document stand-in for testing."""
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}


# ============================================================
# Dummy embedding function (batch callable)
# ============================================================

class DummyEmbeddingFn:
    """LangChain-compatible embedding function, also callable for convenience."""
    def embed_documents(self, texts):
        import numpy as np
        dim = 128
        return [np.random.randn(dim).astype(np.float32).tolist() for _ in texts]

    def __call__(self, texts):
        """Allow direct function-call syntax for pre-computing embeddings."""
        return self.embed_documents(texts)

dummy_embed_fn = DummyEmbeddingFn()


# ============================================================
# FAISSClientWrapper tests
# ============================================================

class TestFAISSClientWrapper:
    """Test FAISS index building, loading, and management."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a FAISSClientWrapper using a temp directory."""
        return FAISSClientWrapper(index_dir=str(tmp_path))

    @pytest.fixture
    def sample_docs(self):
        return [
            FakeDocument("银灰是喀兰贸易的领袖", {"chunk_id": "chunk_1", "collection": "operators"}),
            FakeDocument("初雪是银灰的妹妹", {"chunk_id": "chunk_2", "collection": "operators"}),
            FakeDocument("崖心在罗德岛接受治疗", {"chunk_id": "chunk_3", "collection": "operators"}),
        ]

    def test_init_default_dir(self):
        """Default index_dir should be config.FAISS_INDEX_DIR."""
        client = FAISSClientWrapper()
        assert client.index_dir.exists()

    def test_init_custom_dir(self, tmp_path):
        client = FAISSClientWrapper(index_dir=str(tmp_path))
        assert client.index_dir == tmp_path

    def test_build_and_load_index(self, client, sample_docs):
        """Build index and verify it can be loaded."""
        embeddings = dummy_embed_fn([d.page_content for d in sample_docs])
        client.build_index("test_collection", sample_docs, embeddings=embeddings)

        result = client.load_index("test_collection")
        assert result is not None
        index, meta = result
        assert index.ntotal == 3
        assert len(meta) == 3
        assert meta[0]["page_content"] == "银灰是喀兰贸易的领袖"
        assert meta[0]["metadata"]["chunk_id"] == "chunk_1"

    def test_build_index_requires_embeddings_or_fn(self, client):
        """build_index raises if neither embeddings nor embedding_fn is given."""
        with pytest.raises(ValueError, match="Either embeddings or embedding_fn"):
            client.build_index("test", [FakeDocument("content")])

    def test_build_index_with_embedding_fn(self, client, sample_docs):
        """build_index should work with an embedding function."""
        client.build_index("test_ef", sample_docs, embedding_fn=dummy_embed_fn)
        result = client.load_index("test_ef")
        assert result is not None
        index, _ = result
        assert index.ntotal == 3

    def test_load_nonexistent_collection(self, client):
        result = client.load_index("nonexistent")
        assert result is None

    def test_get_chunk_count(self, client, sample_docs):
        embeddings = dummy_embed_fn([d.page_content for d in sample_docs])
        client.build_index("count_test", sample_docs, embeddings=embeddings)
        assert client.get_chunk_count("count_test") == 3

    def test_get_chunk_count_empty(self, client):
        assert client.get_chunk_count("no_such_collection") == 0

    def test_add_documents_new_collection(self, client, sample_docs):
        """add_documents to a non-existent collection creates it."""
        count = client.add_documents(
            "new_collection", sample_docs, embedding_fn=dummy_embed_fn
        )
        assert count == 3
        assert client.get_chunk_count("new_collection") == 3

    def test_add_documents_incremental(self, client, sample_docs):
        """add_documents to existing collection appends."""
        # First batch
        client.build_index("incr", sample_docs[:2], embedding_fn=dummy_embed_fn)
        assert client.get_chunk_count("incr") == 2

        # Second batch: append
        total = client.add_documents("incr", sample_docs[2:], embedding_fn=dummy_embed_fn)
        assert total == 3
        assert client.get_chunk_count("incr") == 3

    def test_add_documents_requires_embeddings(self, client):
        with pytest.raises(ValueError, match="Either embeddings or embedding_fn"):
            client.add_documents("x", [FakeDocument("content")])

    def test_metadata_saved_correctly(self, client, sample_docs):
        embeddings = dummy_embed_fn([d.page_content for d in sample_docs])
        client.build_index("meta_test", sample_docs, embeddings=embeddings)
        _, meta = client.load_index("meta_test")
        for i, doc in enumerate(sample_docs):
            assert meta[i]["page_content"] == doc.page_content
            assert meta[i]["metadata"]["chunk_id"] == doc.metadata["chunk_id"]

    def test_doc_without_chunk_id_gets_fallback(self, client):
        doc = FakeDocument("内容没有chunk_id", metadata={})
        embeddings = dummy_embed_fn([doc.page_content])
        client.build_index("fallback", [doc], embeddings=embeddings)
        _, meta = client.load_index("fallback")
        assert meta[0]["id"] == "doc_0"

    def test_index_file_exists(self, client, sample_docs):
        embeddings = dummy_embed_fn([d.page_content for d in sample_docs])
        client.build_index("file_test", sample_docs, embeddings=embeddings)
        idx_path = client._index_path("file_test")
        assert idx_path.exists()
        meta_path = client._meta_path("file_test")
        assert meta_path.exists()

    def test_index_dir_created(self, tmp_path):
        nested = tmp_path / "nested" / "index"
        client = FAISSClientWrapper(index_dir=str(nested))
        assert nested.exists()
