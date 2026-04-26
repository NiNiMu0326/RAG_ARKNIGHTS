import json
import os
import re
from pathlib import Path
from typing import List, Dict, Set
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.api.siliconflow import SiliconFlowClient


def _extract_key_sections(content: str) -> tuple:
    """Extract key sections from story content: 关键人物 + 角色剧情概括"""
    lines = content.split('\n')

    # 找到关键人物和角色剧情概括的起始位置
    key_persons_idx = -1
    char_summary_idx = -1

    for i, line in enumerate(lines):
        if '## 关键人物' in line:
            key_persons_idx = i
        elif '## 角色剧情概括' in line or '## 角色剧情概述' in line:
            char_summary_idx = i
            break

    # 提取关键人物
    key_section = ""
    if key_persons_idx >= 0:
        # 找到下一个 ## 标题或文件结束
        for i in range(key_persons_idx + 1, len(lines)):
            if lines[i].startswith('## '):
                break
            key_section += lines[i] + '\n'

    # 提取角色剧情概括
    summary_section = ""
    if char_summary_idx >= 0:
        for i in range(char_summary_idx + 1, len(lines)):
            if lines[i].startswith('## '):
                break
            summary_section += lines[i] + '\n'

    return key_section.strip(), summary_section.strip()


def _parse_key_persons(key_section: str) -> List[str]:
    """Parse key persons from key section - split by ; and clean"""
    if not key_section:
        return []

    # 移除 "关键人物：" 前缀
    key_section = key_section.replace('关键人物：', '').replace('关键人物:', '').strip()

    # 按 ; 分割
    persons = [p.strip() for p in key_section.split(';')]

    # 清理和过滤
    result = []
    for p in persons:
        # 移除空白和括号内容
        p = re.sub(r'\s*\(.*?\)', '', p).strip()

        # 过滤掉不合格的干员名
        if not p or len(p) <= 1:
            continue
        # 排除包含"的"的名字（如"能天使的姐姐"）
        if '的' in p:
            continue
        # 排除过长的名字（可能是描述）
        if len(p) > 15:
            continue
        # 排除明显是描述而非名字的
        if p.startswith('可疑的') or p.startswith('最后的') or p.startswith('沉默的') or p.startswith('好事的神明') or p.startswith('久违的神明') or p.startswith('沉稳的') or p.startswith('温和的') or p.startswith('激动的') or p.startswith('毛茸茸的'):
            continue
        # 排除包含特殊字符的
        if any(c in p for c in '[]{}()""'):
            continue

        result.append(p)

    return result


def _build_prompt(multi_doc_content: str, known_relation_types: List[str], known_operators: List[str] = None) -> str:
    """Build extraction prompt with cumulative known relation types and known operators."""
    # 已知关系类型
    if known_relation_types:
        type_list = ", ".join(f'"{t}"' for t in known_relation_types)
        type_hint = f"\n\n已知关系类型（优先复用，确有必要才创建新类型）：[{type_list}]"
    else:
        type_hint = "\n\n（暂无已知关系类型，请根据文档内容抽取）"

    # 已知干员列表
    if known_operators:
        operators_list = ", ".join(known_operators[:100])  # 限制前100个
        if len(known_operators) > 100:
            operators_list += f" ... 等共{len(known_operators)}个干员"
        operators_hint = f"\n\n已知干员（这些是已识别为干员的实体，抽取关系时可引用，但不要在entities中重复提取）：[{operators_list}]"
    else:
        operators_hint = ""

    return f"""你是一个明日方舟实体关系抽取专家。请从以下多个文档中分别抽取实体和关系。

{type_hint}{operators_hint}

实体类型（必须标注）：
- 干员：游戏中的干员角色（如银灰、凯尔希、阿米娅）—— 不要重复提取，已知干员列表中的不要在entities中重复出现
- 组织：组织、阵营、团体（如罗德岛、喀兰贸易、整合运动）
- 地点：地名、城市、区域（如龙门、哥伦比亚、汐斯卡）
- 事件：剧情事件、战争、活动（如巴别塔事件、维多利亚内战）

关系类型（优先复用已知类型，确有必要才创建新类型）：
- 所属：仅限组织/阵营/团队/企业/国家归属关系（如"银灰"→"喀兰贸易"，"所属"；"博士"→"罗德岛"，"所属"；"阿米娅"→"罗德岛"，"所属"；"陈"→"龙门近卫局"，"所属"）
  ⚠️ 严禁将血缘、师徒、朋友、情感等个人关系标记为"所属"！
- 亲属：血缘/家族/婚姻关系（如"崖心"→"角峰"，"亲属"；"初雪"→"崖心"，"亲属"；"苇草"→"爱布拉娜"，"亲属"）
- 师徒：师徒/导师关系（如"凯尔希"→"阿米娅"，"师徒"；"赫德雷"→"W"，"师徒"）
- 战友：曾经并肩作战的战友（如"银灰"→"陈"，"战友"；"塔露拉"→"爱国者"，"战友"）
- 朋友：朋友/密友关系（如"德克萨斯"→"能天使"，"朋友"；"空"→"可颂"，"朋友"）
- 合作：共同行动、临时合作的关系（如"赫拉格"→"博士"，"合作"；"老鲤"→"梁洵"，"合作"）
- 对立：敌对关系（如"凯尔希"→"特雷西斯"，"对立"；"塔露拉"→"陈"，"对立"）
- 上级：明确的上下级/指挥关系（如"阿米娅"→"博士"，"上级"；"特雷西斯"→"塔露拉"，"上级"）
- 地区：干员与地点的关联（如"银灰"→"维多利亚"，"地区"；"崖心"→"谢拉格"，"地区"）
- 注意：禁止创建"地点"、"事件"、"关系"、"目的地"作为关系类型，这些应该用已有的类型或忽略
- 注意：如果关系描述中出现了"关心"、"思念"、"照顾"等情感词，请使用"朋友"或"合作"类型，不要用"所属"或"剧情"

重要：干员之间的关系非常重要！请准确使用细分类型：
- 血缘/兄妹/姐弟/父女/母子 → 亲属（不是"所属"！不是"剧情"！）
- 师傅/徒弟/导师 → 师徒（不是"所属"！）
- 同事/战友 → 所属（仅限明确同组织）或 战友
- 同一组织成员（如"银灰"→"恩希欧迪斯"，"所属"）
- 关心/思念/照顾等情感 → 朋友 或 合作（不是"所属"！）

直接输出JSON对象（键为文件名），不要任何其他内容。

输出格式：
{{
  "filename1.md": {{
    "entities": [
      {{"entity": "喀兰贸易", "type": "组织"}},
      {{"entity": "维多利亚", "type": "地点"}}
      // 注意：干员实体不要在这里重复提取，已知干员列表中的已在代码中处理
    ],
    "relations": [
      {{"source": "银灰", "target": "喀兰贸易", "relation": "所属", "description": "银灰是喀兰贸易的董事长"}},
      {{"source": "银灰", "target": "维多利亚", "relation": "地区", "description": "银灰常驻于维多利亚"}}
    ]
  }},
  "filename2.md": {{
    "entities": [],
    "relations": []
  }}
}}

文档内容：
{multi_doc_content}

要求：
- 每个文件分别抽取实体和关系
- 实体只提取非干员类型（组织、地点、事件），不要重复提取已知干员
- 关系可以涉及任何实体（干员、组织、地点、事件）
- 关系类型优先复用已知类型
- 实体名只输出简洁核心名称（如"银灰"），不要头衔、职位、Markdown格式
- 禁止实体名中出现以下字符：[ ] {{ }} ( ) 《 》 或完整文件路径
- relations数组可以为空
"""


class EntityExtractor:
    # Use Qwen3 for better JSON output
    EXTRACTION_MODEL = "Qwen/Qwen3-32B"
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

    def extract_batch(self, filepaths: List[str], known_relation_types: List[str] = None,
                      known_operators: List[str] = None, extract_key_sections: bool = False) -> tuple:
        """Extract entities from multiple files in one API call.

        Args:
            filepaths: List of file paths to extract from
            known_relation_types: Known relation types to reuse
            known_operators: Known operator names to avoid duplicate extraction
            extract_key_sections: If True, parse key persons with code + extract relations with LLM

        Returns:
            (results, discovered_relation_types, discovered_operators)
        """
        if known_relation_types is None:
            known_relation_types = []
        if known_operators is None:
            known_operators = []

        try:
            # Build multi-doc content
            doc_parts = []
            file_names = []
            key_persons_list = []  # 存储每个文件的关键人物列表

            for fp in filepaths:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                basename = os.path.basename(fp)
                file_names.append(basename)

                if extract_key_sections:
                    # 返回 (key_section, summary_section)
                    key_section, summary_section = _extract_key_sections(content)
                    # 用代码解析关键人物
                    key_persons = _parse_key_persons(key_section)
                    key_persons_list.append(key_persons)
                    # 只把角色剧情概括给 LLM
                    doc_parts.append(f"=== {basename} ===\n角色剧情概括：\n{summary_section}")
                else:
                    key_persons_list.append([])
                    extracted = content[:self.MAX_CHARS_PER_DOC]
                    doc_parts.append(f"=== {basename} ===\n{extracted}")

            multi_doc = "\n\n".join(doc_parts)
            prompt = _build_prompt(multi_doc, known_relation_types, known_operators)

            response = self.client.chat([
                {"role": "system", "content": "你是一个明日方舟实体关系抽取专家。直接输出JSON对象，不要其他内容。"},
                {"role": "user", "content": prompt}
            ], model=self.EXTRACTION_MODEL)

            results = self._parse_batch_result(response, file_names)

            # 收集本批发现的新干员（从关键人物中）
            new_operators = set()
            for key_persons in key_persons_list:
                for person in key_persons:
                    if person not in known_operators:
                        new_operators.add(person)

            # 如果使用 key_sections 模式，把代码解析的关键人物合并到结果中
            if extract_key_sections:
                for i, result in enumerate(results):
                    if i < len(key_persons_list):
                        key_persons = key_persons_list[i]
                        # 添加关键人物作为干员实体（只添加新发现的）
                        for person in key_persons:
                            # 检查是否已存在
                            existing = [e for e in result.get('entities', []) if e['entity'] == person]
                            if not existing:
                                result['entities'].append({'entity': person, 'type': '干员'})

            # Collect all relation types found in this batch (including new ones)
            batch_types = set()
            for result in results:
                for rel in result.get('relations', []):
                    rel_type = rel.get('relation', '').strip()
                    if rel_type:
                        batch_types.add(rel_type)

            return results, list(batch_types), list(new_operators)

        except Exception as e:
            return [{'source_file': os.path.basename(fp), 'entities': [], 'relations': [], 'error': str(e)} for fp in filepaths], [], []

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
        known_operators: List[str] = []  # cumulative known operators

        # Process operators/
        op_files = sorted(Path(operators_dir).glob('*.md'))
        print(f"Extracting from {len(op_files)} operator files (batch={batch_size}, initial types={len(known_relation_types)})...")

        for i in range(0, len(op_files), batch_size):
            batch = op_files[i:i+batch_size]
            results, batch_types, new_ops = self.extract_batch(
                [str(f) for f in batch],
                known_relation_types,
                known_operators,
                extract_key_sections=False
            )

            for result in results:
                all_entities.extend(result.get('entities', []))
                all_relations.extend(result.get('relations', []))

            # 累积已发现的干员
            for op in new_ops:
                if op not in known_operators:
                    known_operators.append(op)

            # Update known types: add new ones discovered this batch
            new_types = [t for t in batch_types if t not in known_relation_types]
            if new_types:
                known_relation_types.extend(new_types)

            processed = min(i + batch_size, len(op_files))
            print(f"  Processed {processed}/{len(op_files)} | 干员: {len(known_operators)} | 关系类型: {len(known_relation_types)}")

        # Deduplicate and save
        return self._deduplicate_and_save(all_entities, all_relations, output_path)

    def extract_all_stories(self, stories_dir: str, output_path: str, batch_size: int = None):
        """Extract entities from story files using batch API calls.

        Only extracts from 关键人物 + 角色剧情概括 sections.
        """
        if batch_size is None:
            batch_size = self.BATCH_SIZE

        all_entities = []
        all_relations = []
        known_relation_types: List[str] = []  # cumulative
        known_operators: List[str] = []  # cumulative known operators

        # Process stories/
        story_files = sorted(Path(stories_dir).glob('*.md'))
        print(f"Extracting from {len(story_files)} story files (batch={batch_size})...")

        for i in range(0, len(story_files), batch_size):
            batch = story_files[i:i+batch_size]
            results, batch_types, new_operators = self.extract_batch(
                [str(f) for f in batch],
                known_relation_types,
                known_operators,
                extract_key_sections=True
            )

            for result in results:
                all_entities.extend(result.get('entities', []))
                all_relations.extend(result.get('relations', []))

            # 累积已发现的干员
            for op in new_operators:
                if op not in known_operators:
                    known_operators.append(op)

            new_types = [t for t in batch_types if t not in known_relation_types]
            if new_types:
                known_relation_types.extend(new_types)

            processed = min(i + batch_size, len(story_files))
            print(f"  Processed {processed}/{len(story_files)} | 干员: {len(known_operators)} | 关系类型: {len(known_relation_types)}")

        # Deduplicate and save
        return self._deduplicate_and_save(all_entities, all_relations, output_path)

    def _deduplicate_and_save(self, all_entities: List, all_relations: List, output_path: str) -> Dict:
        """Deduplicate entities and relations, then save to file."""
        # Deduplicate
        seen_entities: Set[str] = set()
        unique_entities = []
        for e in all_entities:
            name = e['entity'].strip()
            if not name or any(c in name for c in "[]{}()"):
                continue
            if name not in seen_entities:
                seen_entities.add(name)
                unique_entities.append(e)

        seen_relations = set()
        unique_relations = []
        for r in all_relations:
            src, tgt, rel = r.get('source', '').strip(), r.get('target', '').strip(), r.get('relation', '').strip()
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

        print(f"\nDone! {len(unique_entities)} entities, {len(unique_relations)} relations")
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
