import json
import os
from pathlib import Path
from typing import List, Dict, Set
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.api.siliconflow import SiliconFlowClient

def _build_prompt(multi_doc_content: str, known_relation_types: List[str]) -> str:
    """Build extraction prompt with cumulative known relation types."""
    if known_relation_types:
        type_list = ", ".join(f'"{t}"' for t in known_relation_types)
        type_hint = f"\n\n已知关系类型（优先复用，确有必要才创建新类型）：[{type_list}]"
    else:
        type_hint = "\n\n（暂无已知关系类型，请根据文档内容抽取）"

    return f"""你是一个明日方舟干员实体关系抽取专家。请从以下多个文档中分别抽取干员实体和关系。

{type_hint}

直接输出JSON对象（键为文件名），不要任何其他内容。

输出格式：
{{
  "filename1.md": {{
    "entities": [{{"entity": "干员名", "type": "干员"}}],
    "relations": [{{"source": "干员A", "target": "干员B", "relation": "关系", "description": "描述"}}]
  }},
  "filename2.md": {{
    "entities": [{{"entity": "干员名", "type": "干员"}}],
    "relations": []
  }}
}}

文档内容：
{multi_doc_content}

要求：
- 每个文件分别抽取实体和关系
- 只抽取真实存在于文档中的关系
- 关系类型优先复用已知类型，确有必要才创建新类型（最多创建1-2个）
- 实体名只输出简洁核心名称（如"银灰"），不要头衔、职位、Markdown格式
- 禁止实体名中出现以下字符：[ ] {{ }} ( ) 《 》 或完整文件路径
- relations数组可以为空
"""

class EntityExtractor:
    # Use fast model for entity extraction (offline batch job)
    EXTRACTION_MODEL = "Qwen/Qwen2.5-7B-Instruct"
    # Docs per API call
    BATCH_SIZE = 10
    # Chars per document in batch mode
    MAX_CHARS_PER_DOC = 1500

    def __init__(self, api_key: str = None):
        self.client = SiliconFlowClient(api_key)

    def _parse_batch_result(self, response: str, file_names: List[str]) -> List[Dict]:
        """Parse batch extraction result with new {entities, relations} format."""
        json_str = response.strip()
        if json_str.startswith("```"):
            lines = json_str.split('\n')
            json_str = '\n'.join(lines[1:-1])
        elif json_str.startswith("```json"):
            lines = json_str.split('\n')
            json_str = '\n'.join(lines[1:-1])

        data = json.loads(json_str)

        results = []
        for fname in file_names:
            file_data = data.get(fname, {})
            entities = []
            relations = []

            # New format: {"entities": [...], "relations": [...]}
            if isinstance(file_data, dict):
                for item in file_data.get('entities', []):
                    if isinstance(item, dict):
                        entities.append({'entity': item.get('entity', ''), 'type': item.get('type', '干员')})
                for item in file_data.get('relations', []):
                    if isinstance(item, dict) and 'source' in item and 'target' in item:
                        relations.append(item)
            # Fallback: flat list
            elif isinstance(file_data, list):
                for item in file_data:
                    if isinstance(item, dict):
                        if 'entity' in item:
                            entities.append({'entity': item['entity'], 'type': item.get('type', '干员')})
                        elif 'source' in item and 'target' in item:
                            relations.append(item)

            results.append({
                'source_file': fname,
                'entities': entities,
                'relations': relations
            })
        return results

    def extract_batch(self, filepaths: List[str], known_relation_types: List[str] = None) -> tuple:
        """Extract entities from multiple files in one API call.

        Returns:
            (results, discovered_relation_types) where discovered_relation_types
            are new types found in this batch not in known_relation_types.
        """
        if known_relation_types is None:
            known_relation_types = []

        try:
            # Build multi-doc content
            doc_parts = []
            file_names = []
            for fp in filepaths:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                basename = os.path.basename(fp)
                file_names.append(basename)
                truncated = content[:self.MAX_CHARS_PER_DOC]
                doc_parts.append(f"=== {basename} ===\n{truncated}")

            multi_doc = "\n\n".join(doc_parts)
            prompt = _build_prompt(multi_doc, known_relation_types)

            response = self.client.chat([
                {"role": "system", "content": "你是一个明日方舟干员实体关系抽取专家。直接输出JSON对象，不要其他内容。"},
                {"role": "user", "content": prompt}
            ], model=self.EXTRACTION_MODEL)

            results = self._parse_batch_result(response, file_names)

            # Collect all relation types found in this batch (including new ones)
            batch_types = set()
            for result in results:
                for rel in result.get('relations', []):
                    rel_type = rel.get('relation', '').strip()
                    if rel_type:
                        batch_types.add(rel_type)

            return results, list(batch_types)

        except Exception as e:
            return [{'source_file': os.path.basename(fp), 'entities': [], 'relations': [], 'error': str(e)} for fp in filepaths], []

    def extract_from_text(self, text: str, source_file: str) -> Dict:
        """Extract entities and relations from a single document text."""
        try:
            prompt = f"""你是一个明日方舟干员实体关系抽取专家。请从以下文档中抽取干员实体和关系。

直接输出JSON数组，不要任何其他内容。

输出格式：
[{{"entity": "干员名", "type": "干员"}}, {{"source": "干员A", "target": "干员B", "relation": "关系", "description": "描述"}}]

文档内容：
{text[:8000]}

要求：
- 只抽取真实存在于文档中的关系
- 如果没有干员关系，返回空数组[]
"""
            response = self.client.chat([
                {"role": "system", "content": "你是一个明日方舟干员实体关系抽取专家。直接输出JSON数组，不要其他内容。"},
                {"role": "user", "content": prompt}
            ], model=self.EXTRACTION_MODEL)

            json_str = response.strip()
            if json_str.startswith("```"):
                lines = json_str.split('\n')
                json_str = '\n'.join(lines[1:-1])
            elif json_str.startswith("```json"):
                lines = json_str.split('\n')
                json_str = '\n'.join(lines[1:-1])

            data = json.loads(json_str)

            entities = []
            relations = []

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if 'entity' in item:
                            entities.append({'entity': item['entity'], 'type': item.get('type', '干员')})
                        elif 'source' in item and 'target' in item:
                            relations.append(item)
            elif isinstance(data, dict):
                if 'name' in data and 'relations' in data:
                    main_entity = data['name']
                    entities.append({'entity': main_entity, 'type': '干员'})
                    for rel in data.get('relations', []):
                        if isinstance(rel, dict) and 'name' in rel:
                            entities.append({'entity': rel['name'], 'type': '干员'})
                            relations.append({
                                'source': main_entity,
                                'target': rel['name'],
                                'relation': rel.get('relation', ''),
                                'description': rel.get('description', '')
                            })
                elif 'entities' in data or 'relations' in data:
                    for item in data.get('entities', []):
                        if isinstance(item, dict):
                            entities.append({'entity': item.get('name', item.get('entity', '')), 'type': '干员'})
                    for item in data.get('relations', []):
                        if isinstance(item, dict) and 'source' in item and 'target' in item:
                            relations.append(item)

            return {
                'source_file': source_file,
                'entities': entities,
                'relations': relations
            }
        except Exception as e:
            return {
                'source_file': source_file,
                'entities': [],
                'relations': [],
                'error': str(e)
            }

    def extract_from_file(self, filepath: str) -> Dict:
        """Extract entities from a single md file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.extract_from_text(content, os.path.basename(filepath))

    def extract_all(self, operators_dir: str, output_path: str, batch_size: int = None):
        """Extract entities from operator files using batch API calls with cumulative relation types.

        Only processes operators (no stories) to keep the knowledge graph clean.
        Relation types discovered in earlier batches are fed into later prompts.
        """
        if batch_size is None:
            batch_size = self.BATCH_SIZE

        all_entities = []
        all_relations = []
        known_relation_types: List[str] = []  # cumulative

        # Process operators/
        op_files = sorted(Path(operators_dir).glob('*.md'))
        print(f"Extracting from {len(op_files)} operator files (batch={batch_size}, initial types={len(known_relation_types)})...")

        for i in range(0, len(op_files), batch_size):
            batch = op_files[i:i+batch_size]
            results, batch_types = self.extract_batch([str(f) for f in batch], known_relation_types)

            for result in results:
                all_entities.extend(result.get('entities', []))
                all_relations.extend(result.get('relations', []))

            # Update known types: add new ones discovered this batch
            new_types = [t for t in batch_types if t not in known_relation_types]
            if new_types:
                known_relation_types.extend(new_types)

            processed = min(i + batch_size, len(op_files))
            print(f"  Processed {processed}/{len(op_files)} | known relation types: {len(known_relation_types)} | new this batch: {len(new_types)}")

        # Deduplicate
        seen_entities: Set[str] = set()
        unique_entities = []
        for e in all_entities:
            name = e['entity'].strip()
            # Skip malformed entity names
            if not name or any(c in name for c in "[]{}()"):
                continue
            if name not in seen_entities:
                seen_entities.add(name)
                unique_entities.append(e)

        seen_relations = set()
        unique_relations = []
        for r in all_relations:
            src, tgt, rel = r.get('source', '').strip(), r.get('target', '').strip(), r.get('relation', '').strip()
            # Skip malformed
            if not src or not tgt or not rel:
                continue
            if any(c in src or c in tgt for c in "[]{}()"):
                continue
            key = (src, tgt, rel)
            if key not in seen_relations:
                seen_relations.add(key)
                unique_relations.append(r)

        result_data = {
            'entities': unique_entities,
            'relations': unique_relations
        }

        # Save
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        print(f"\nDone! {len(unique_entities)} entities, {len(unique_relations)} relations, {len(known_relation_types)} relation types")
        print(f"Saved to {output_path}")
        return result_data

if __name__ == "__main__":
    import sys
    if '--force' in sys.argv or len(sys.argv) > 1 and sys.argv[1] == 'y':
        force = True
    else:
        print("WARNING: This will make API calls for ~835 operator files (no stories).")
        confirm = input("Continue? (y/n): ")
        force = confirm.lower() == 'y'

    if force:
        extractor = EntityExtractor()
        extractor.extract_all(
            operators_dir=str(Path(__file__).parent.parent.parent / 'data/operators'),
            output_path=str(Path(__file__).parent.parent.parent / 'chunks/graphrag/entity_relations.json')
        )