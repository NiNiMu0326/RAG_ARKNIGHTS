import os
from pathlib import Path
from typing import List, Dict
import config
from backend.api.siliconflow import SiliconFlowClient
from backend.storage.chroma_client import ChromaClientWrapper
from backend.data.bm25_index import BM25Indexer

class IndexManager:
    def __init__(self, api_key: str = None):
        self.client = SiliconFlowClient(api_key)
        self.chroma = ChromaClientWrapper(embedding_client=self.client)
        self.collection_chunks = {}  # collection_name -> list of chunk dicts

    def build_all_indexes(self, force: bool = False):
        """Build Chroma indexes for all 3 collections by embedding chunk texts."""
        collections = ['operators', 'stories', 'knowledge']

        for coll_name in collections:
            # Check if already built
            existing = self.chroma.get_chunk_count(coll_name)
            chunks_dir = str(Path(__file__).parent.parent.parent / 'chunks' / coll_name)

            if not force and existing > 0:
                print(f"Collection '{coll_name}' already has {existing} chunks, skipping. Use force=True to rebuild.")
                continue

            # Load chunks
            chunk_files = list(Path(chunks_dir).glob('*.md')) + list(Path(chunks_dir).glob('*.txt'))
            chunk_files.sort()

            chunks = []
            for path in chunk_files:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                chunk_id = path.stem  # filename without extension
                chunks.append({
                    'chunk_id': chunk_id,
                    'content': content,
                    'section': chunk_id,
                    'source_file': path.name
                })

            print(f"Embedding {len(chunks)} chunks for collection '{coll_name}'...")

            # Create collection
            self.chroma.create_collection(coll_name)

            # Batch embed and add to Chroma (batch size 20 to avoid 413)
            batch_size = 20
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                texts = [c['content'] for c in batch]

                # Embed
                embeddings = self.client.embed(texts)

                # Add to collection with embeddings
                coll = self.chroma.get_collection(coll_name)
                ids = [c['chunk_id'] for c in batch]
                documents = [c['content'] for c in batch]
                metadatas = [{'section': c.get('section', ''), 'source_file': c.get('source_file', '')} for c in batch]

                coll.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings
                )

                print(f"  Indexed {min(i+batch_size, len(chunks))}/{len(chunks)}")

            self.collection_chunks[coll_name] = chunks
            print(f"Built index for '{coll_name}': {len(chunks)} chunks")

    def load_indexes(self):
        """Load existing indexes (verify Chroma is accessible)."""
        for coll_name in ['operators', 'stories', 'knowledge']:
            try:
                count = self.chroma.get_chunk_count(coll_name)
                print(f"Collection '{coll_name}': {count} chunks")
            except Exception as e:
                print(f"Collection '{coll_name}': not found ({e})")

    def search(self, collection_name: str, query: str, n_results: int = 10) -> List[Dict]:
        """Search a collection using vector similarity."""
        return self.chroma.search(collection_name, query, n_results)

    def rebuild_if_needed(self):
        """Rebuild indexes if they are missing or empty."""
        for coll_name in ['operators', 'stories', 'knowledge']:
            count = self.chroma.get_chunk_count(coll_name)
            if count == 0:
                print(f"Collection '{coll_name}' is empty, building index...")
                self.build_all_indexes(force=True)
            else:
                print(f"Collection '{coll_name}' has {count} chunks, skipping.")

if __name__ == "__main__":
    manager = IndexManager()
    print("Building all Chroma indexes (this will embed ~13k chunks via SiliconFlow API)...")
    print("WARNING: This will make many API calls and may take several minutes.")
    confirm = input("Continue? (y/n): ")
    if confirm.lower() == 'y':
        manager.build_all_indexes(force=True)
    else:
        print("Cancelled.")