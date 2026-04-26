"""
Build GraphRAG knowledge graph by extracting entity relations from operator and story files.
Run this script to build the entity_relations.json file for knowledge graph queries.

Usage:
    python backend/build_graphrag.py              # Interactive mode
    python backend/build_graphrag.py operators    # Extract only from operators
    python backend/build_graphrag.py stories      # Extract only from stories
    python backend/build_graphrag.py all          # Extract from both (default)
"""
import sys
import os
from pathlib import Path

# Setup path
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from backend.rag.graphrag.extractor import EntityExtractor
from backend import config


def build_operators():
    """Build GraphRAG from operator files."""
    extractor = EntityExtractor()
    output_path = config.ENTITY_RELATIONS_FILE
    operators_dir = config.DATA_DIR / 'operators'
    
    print(f"=== Extracting from operators ===")
    print(f"Input: {operators_dir}")
    print(f"Output: {output_path}")
    
    result = extractor.extract_all(
        operators_dir=str(operators_dir),
        output_path=str(output_path)
    )
    return result


def build_stories():
    """Build GraphRAG from story files (extracts key persons + relations)."""
    extractor = EntityExtractor()
    output_path = SCRIPT_DIR / 'chunks' / 'graphrag' / 'entity_relations.json'
    stories_dir = SCRIPT_DIR.parent / 'data' / 'stories'
    
    print(f"=== Extracting from stories ===")
    print(f"Input: {stories_dir}")
    print(f"Output: {output_path}")
    
    result = extractor.extract_all_stories(
        stories_dir=str(stories_dir),
        output_path=str(output_path)
    )
    return result


def build_all():
    """Build GraphRAG from both operators and stories."""
    extractor = EntityExtractor()
    output_path = SCRIPT_DIR / 'chunks' / 'graphrag' / 'entity_relations.json'
    operators_dir = SCRIPT_DIR.parent / 'data' / 'operators'
    stories_dir = SCRIPT_DIR.parent / 'data' / 'stories'
    
    print("=== Extracting from operators ===")
    print(f"Input: {operators_dir}")
    
    all_entities = []
    all_relations = []
    known_relation_types = []
    
    # Extract from operators
    op_files = sorted(Path(operators_dir).glob('*.md'))
    print(f"Processing {len(op_files)} operator files...")
    
    for i in range(0, len(op_files), extractor.BATCH_SIZE):
        batch = op_files[i:i+extractor.BATCH_SIZE]
        results, batch_types = extractor.extract_batch(
            [str(f) for f in batch], 
            known_relation_types,
            extract_key_sections=False
        )
        
        for result in results:
            all_entities.extend(result.get('entities', []))
            all_relations.extend(result.get('relations', []))
        
        new_types = [t for t in batch_types if t not in known_relation_types]
        if new_types:
            known_relation_types.extend(new_types)
        
        processed = min(i + extractor.BATCH_SIZE, len(op_files))
        print(f"  Processed {processed}/{len(op_files)} | types: {len(known_relation_types)}")
    
    print("\n=== Extracting from stories ===")
    print(f"Input: {stories_dir}")
    
    story_files = sorted(Path(stories_dir).glob('*.md'))
    print(f"Processing {len(story_files)} story files...")
    
    for i in range(0, len(story_files), extractor.BATCH_SIZE):
        batch = story_files[i:i+extractor.BATCH_SIZE]
        results, batch_types = extractor.extract_batch(
            [str(f) for f in batch], 
            known_relation_types,
            extract_key_sections=True
        )
        
        for result in results:
            all_entities.extend(result.get('entities', []))
            all_relations.extend(result.get('relations', []))
        
        new_types = [t for t in batch_types if t not in known_relation_types]
        if new_types:
            known_relation_types.extend(new_types)
        
        processed = min(i + extractor.BATCH_SIZE, len(story_files))
        print(f"  Processed {processed}/{len(story_files)} | types: {len(known_relation_types)}")
    
    # Deduplicate and save
    return extractor._deduplicate_and_save(all_entities, all_relations, str(output_path), known_relation_types)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    
    if mode == 'operators':
        print("WARNING: This will make API calls for ~826 operator files.")
        confirm = input("Continue? (y/n): ")
        if confirm.lower() == 'y':
            build_operators()
    elif mode == 'stories':
        print("WARNING: This will make API calls for ~451 story files.")
        confirm = input("Continue? (y/n): ")
        if confirm.lower() == 'y':
            build_stories()
    elif mode == 'all':
        print("WARNING: This will make API calls for ~826 operators + ~451 stories files.")
        confirm = input("Continue? (y/n): ")
        if confirm.lower() == 'y':
            build_all()
    else:
        print("Usage:")
        print("  python build_graphrag.py              # Show this help")
        print("  python build_graphrag.py operators    # Extract from operators only")
        print("  python build_graphrag.py stories     # Extract from stories only")
        print("  python build_graphrag.py all         # Extract from both (all)")
