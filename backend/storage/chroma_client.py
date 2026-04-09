import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional

# Try to import config, but allow fallback for testing
try:
    import config
    DEFAULT_CHROMA_DIR = config.CHROMA_PERSIST_DIR
except (ImportError, ValueError):
    DEFAULT_CHROMA_DIR = "./chroma_db"

class ChromaClientWrapper:
    def __init__(self, persist_dir: str = None, embedding_client=None):
        """Initialize ChromaDB client.

        Args:
            persist_dir: Directory for ChromaDB persistence
            embedding_client: SiliconFlowClient instance for embedding queries.
                              If None, search() must be called with explicit embeddings.
        """
        self.persist_dir = persist_dir or DEFAULT_CHROMA_DIR
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collections = {}
        self._embedding_client = embedding_client

    def create_collection(self, name: str, get_or_create: bool = True):
        """Create or get a collection."""
        coll = self.client.get_or_create_collection(name=name)
        self.collections[name] = coll
        return coll

    def get_collection(self, name: str):
        """Get an existing collection."""
        return self.client.get_collection(name=name)

    def add_chunks(self, collection_name: str, chunks: List[Dict]):
        """Add chunks to a collection.

        Each chunk dict should have: chunk_id, content, section, source_file
        """
        coll = self.get_collection(collection_name)
        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for chunk in chunks:
            ids.append(chunk['chunk_id'])
            documents.append(chunk['content'])
            metadatas.append({
                'section': chunk.get('section', ''),
                'source_file': chunk.get('source_file', '')
            })

        coll.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

    def search(self, collection_name: str, query: str, n_results: int = 10,
               embeddings: List[List[float]] = None) -> List[Dict]:
        """Search collection by query text or pre-computed embeddings.

        If embedding_client is available, queries are automatically embedded using it.
        Otherwise, explicit embeddings must be provided.
        """
        coll = self.get_collection(collection_name)
        query_embeddings = embeddings
        if query_embeddings is None:
            if self._embedding_client is not None:
                query_embeddings = self._embedding_client.embed([query])
            else:
                # Fallback: use query_texts (relies on ChromaDB's internal embedder)
                # This may cause dimension mismatch if internal model differs
                results = coll.query(
                    query_texts=[query],
                    n_results=n_results
                )
                return self._format_results(results)

        results = coll.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )
        return self._format_results(results)

    def search_with_scores(self, collection_name: str, query_embedding: List[float],
                          n_results: int = 10) -> List[Dict]:
        """Search with pre-computed embedding and return results with distances."""
        coll = self.get_collection(collection_name)
        results = coll.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=['distances', 'documents', 'metadatas']
        )
        return self._format_results(results)

    def _format_results(self, results) -> List[Dict]:
        """Format Chroma results into a cleaner structure."""
        formatted = []
        if not results['ids'] or not results['ids'][0]:
            return formatted

        for i, doc_id in enumerate(results['ids'][0]):
            formatted.append({
                'chunk_id': doc_id,
                'content': results['documents'][0][i] if 'documents' in results else '',
                'distance': results['distances'][0][i] if 'distances' in results else 0.0,
                'metadata': results['metadatas'][0][i] if 'metadatas' in results else {}
            })
        return formatted

    def get_chunk_count(self, collection_name: str) -> int:
        """Get number of chunks in a collection."""
        try:
            coll = self.get_collection(collection_name)
            return coll.count()
        except (ValueError, chromadb.errors.NotFoundError):
            return 0