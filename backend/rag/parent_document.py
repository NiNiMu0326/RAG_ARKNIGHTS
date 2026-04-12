import time
from pathlib import Path
from typing import List, Dict, Optional
from collections import OrderedDict

class LRUCache:
    """Simple LRU cache with size limit and optional TTL."""
    def __init__(self, max_size: int = 100, ttl_seconds: float = None):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds  # Time-to-live in seconds

    def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            # Check expiration
            if self._ttl_seconds is not None:
                entry = self._cache[key]
                if time.time() - entry['timestamp'] > self._ttl_seconds:
                    del self._cache[key]
                    return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]['value'] if self._ttl_seconds else self._cache[key]
        return None

    def set(self, key: str, value: str) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                # Remove least recently used item
                self._cache.popitem(last=False)
        if self._ttl_seconds:
            self._cache[key] = {'value': value, 'timestamp': time.time()}
        else:
            self._cache[key] = value

    def __contains__(self, key: str) -> bool:
        if key in self._cache:
            if self._ttl_seconds is not None:
                entry = self._cache[key]
                if time.time() - entry['timestamp'] > self._ttl_seconds:
                    del self._cache[key]
                    return False
            return True
        return False

    def __len__(self) -> int:
        return len(self._cache)


class ParentDocumentRetriever:
    def __init__(self, chunks_dir: str = None, data_dir: str = None):
        from backend import config as _cfg
        self.chunks_dir = chunks_dir or str(_cfg.CHUNKS_DIR)
        self.data_dir = data_dir or str(_cfg.DATA_DIR)
        # LRU cache for loaded parent documents (max 100 entries, 5 hour TTL)
        # 5 hours = 5 * 60 * 60 = 18000 seconds
        self._doc_cache = LRUCache(max_size=100, ttl_seconds=18000)
        # Cache for operator index mapping (file_idx -> filename) with 1 hour TTL
        self._operators_index_cache = None
        self._operators_index_timestamp = None
        self._stories_index_cache = None
        self._stories_index_timestamp = None
        self._INDEX_CACHE_TTL = 3600  # 1 hour TTL

    def _build_operators_index(self) -> Dict[int, str]:
        """Build mapping from operator index to source filename.

        Files are sorted alphabetically and indexed starting from 1.
        So operators_0001 corresponds to the first file alphabetically.
        """
        current_time = time.time()

        # Check if cache is still valid
        if (self._operators_index_cache is not None and
            self._operators_index_timestamp is not None and
            current_time - self._operators_index_timestamp < self._INDEX_CACHE_TTL):
            return self._operators_index_cache

        operators_dir = Path(self.data_dir) / 'operators'
        if not operators_dir.exists():
            self._operators_index_cache = {}
            self._operators_index_timestamp = current_time
            return self._operators_index_cache

        # Get all .md files sorted alphabetically
        files = sorted([f.name for f in operators_dir.glob('*.md') if f.name.endswith('.md')])

        # Build index: 1-based index -> filename
        self._operators_index_cache = {i + 1: f for i, f in enumerate(files)}
        self._operators_index_timestamp = current_time
        return self._operators_index_cache

    def _build_stories_index(self) -> Dict[int, str]:
        """Build mapping from story index to source filename."""
        current_time = time.time()

        # Check if cache is still valid
        if (self._stories_index_cache is not None and
            self._stories_index_timestamp is not None and
            current_time - self._stories_index_timestamp < self._INDEX_CACHE_TTL):
            return self._stories_index_cache

        stories_dir = Path(self.data_dir) / 'stories'
        if not stories_dir.exists():
            self._stories_index_cache = {}
            self._stories_index_timestamp = current_time
            return self._stories_index_cache

        # Get all .md files sorted alphabetically
        files = sorted([f.name for f in stories_dir.glob('*.md') if f.name.endswith('.md')])

        # Build index: 1-based index -> filename
        self._stories_index_cache = {i + 1: f for i, f in enumerate(files)}
        self._stories_index_timestamp = current_time
        return self._stories_index_cache

    def _get_parent_file(self, chunk_id: str, source: str) -> str:
        """Map a chunk_id to its source file name.

        For operators/stories chunks:
        - Extract the base index from chunk_id (e.g., operators_0001_01 -> 0001)
        - Look up the source file using the built index

        Args:
            chunk_id: e.g., 'operators_0001_01' or 'stories_0001_01'
            source: 'operators' or 'stories'

        Returns:
            Source filename, e.g., 'char_002_amiya.md'
        """
        # Parse chunk_id to extract base index
        # Format: source_XXXX or source_XXXX_YY or source_XXXX_YY_ZZ
        parts = chunk_id.split('_')
        if len(parts) < 2:
            return None

        try:
            base_idx = int(parts[1])
        except ValueError:
            return None

        if source == 'operators':
            index_map = self._build_operators_index()
        elif source == 'stories':
            index_map = self._build_stories_index()
        else:
            return None

        return index_map.get(base_idx)

    def get_parent_content(self, chunk: Dict, source: str) -> str:
        """Get the full parent document content for a chunk.

        Args:
            chunk: Chunk dict with chunk_id, metadata, etc.
            source: 'operators' or 'stories'

        Returns:
            Full content of the parent document, or chunk content if not found.
        """
        metadata = chunk.get('metadata', {})
        source_file = metadata.get('source_file', '')

        # If no source_file in metadata, try to derive from chunk_id
        if not source_file:
            source_file = self._get_parent_file(chunk.get('chunk_id', ''), source)

        if not source_file:
            return chunk.get('content', '')

        # Build path to original source
        if source == 'operators':
            source_dir = Path(self.data_dir) / 'operators'
        elif source == 'stories':
            source_dir = Path(self.data_dir) / 'stories'
        else:
            return chunk.get('content', '')

        source_path = source_dir / source_file
        if source_path.exists():
            # Check cache first
            cache_key = f"{source}:{source_file}"
            cached = self._doc_cache.get(cache_key)
            if cached is not None:
                return cached

            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._doc_cache.set(cache_key, content)
            return content

        return chunk.get('content', '')

    def retrieve_parent_docs(self, chunks: List[Dict], source: str) -> List[Dict]:
        """Take a list of chunk results and return full parent documents.

        Args:
            chunks: List of chunk dicts from search results
            source: 'operators' or 'stories'

        Returns:
            List of dicts with chunk_id, parent_content, metadata, score, source
        """
        results = []
        for chunk in chunks:
            parent_content = self.get_parent_content(chunk, source)
            results.append({
                'chunk_id': chunk.get('chunk_id', ''),
                'parent_content': parent_content,
                'metadata': chunk.get('metadata', {}),
                'score': chunk.get('score', 0.0),
                'source': source,
                'section': chunk.get('metadata', {}).get('section', '')
            })
        return results
