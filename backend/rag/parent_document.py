import os
from pathlib import Path
from typing import List, Dict, Optional

class ParentDocumentRetriever:
    def __init__(self, chunks_dir: str = None, data_dir: str = None):
        self.chunks_dir = chunks_dir or str(Path(__file__).parent.parent / 'chunks')
        self.data_dir = data_dir or str(Path(__file__).parent.parent / 'data')
        # Cache for loaded parent documents
        self._doc_cache = {}
        # Cache for operator index mapping (file_idx -> filename)
        self._operators_index_cache = None
        self._stories_index_cache = None

    def _build_operators_index(self) -> Dict[int, str]:
        """Build mapping from operator index to source filename.

        Files are sorted alphabetically and indexed starting from 1.
        So operators_0001 corresponds to the first file alphabetically.
        """
        if self._operators_index_cache is not None:
            return self._operators_index_cache

        operators_dir = Path(self.data_dir) / 'operators'
        if not operators_dir.exists():
            self._operators_index_cache = {}
            return self._operators_index_cache

        # Get all .md files sorted alphabetically
        files = sorted([f.name for f in operators_dir.glob('*.md') if f.name.endswith('.md')])

        # Build index: 1-based index -> filename
        self._operators_index_cache = {i + 1: f for i, f in enumerate(files)}
        return self._operators_index_cache

    def _build_stories_index(self) -> Dict[int, str]:
        """Build mapping from story index to source filename.

        Files are sorted alphabetically and indexed starting from 1.
        """
        if self._stories_index_cache is not None:
            return self._stories_index_cache

        stories_dir = Path(self.data_dir) / 'stories'
        if not stories_dir.exists():
            self._stories_index_cache = {}
            return self._stories_index_cache

        # Get all .md files sorted alphabetically
        files = sorted([f.name for f in stories_dir.glob('*.md') if f.name.endswith('.md')])

        # Build index: 1-based index -> filename
        self._stories_index_cache = {i + 1: f for i, f in enumerate(files)}
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
            if cache_key in self._doc_cache:
                return self._doc_cache[cache_key]

            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._doc_cache[cache_key] = content
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