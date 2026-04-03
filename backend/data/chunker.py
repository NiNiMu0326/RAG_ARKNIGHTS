import os
import re
import json
import shutil
from typing import List, Dict, Any
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CHUNKS_DIR = BASE_DIR / "chunks"

def json_to_text(obj: Dict[str, Any]) -> str:
    lines = []
    for key, value in obj.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            value = "、".join(str(v) for v in value)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)

def load_all_operators(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_all_enemies(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_operators_summary(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_memes(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_gameplay(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_md_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def split_by_sections(content: str) -> List[tuple]:
    """Split markdown content by ## headers. Returns [(section_name, content), ...]"""
    pattern = r'\n##\s+(.+?)\n'
    parts = re.split(pattern, content)
    result = []
    if parts[0].strip() and parts[0].strip() != '#':
        result.append(("开头", parts[0]))
    for i in range(1, len(parts), 2):
        if i+1 < len(parts):
            result.append((parts[i].strip(), parts[i+1]))
    return result

def split_long_text(text: str, max_chars: int = 1500) -> List[str]:
    """Split long text at paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) <= max_chars:
            current += "\n\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks

def chunk_operators_file(content: str, filename: str, base_idx: int) -> List[Dict]:
    """Split operator md by ## sections."""
    sections = split_by_sections(content)
    sections = _merge_tiny_sections(sections, min_len=500)

    chunks = []
    for i, (sec_name, sec_content) in enumerate(sections):
        if not sec_content.strip():
            continue
        if len(sec_content) > 1500:
            sub_chunks = split_long_text(sec_content, max_chars=1500)
            for j, sub in enumerate(sub_chunks):
                chunk_id = f"operators_{base_idx:04d}_{i+1:02d}_{j+1:02d}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "section": sec_name,
                    "content": sub.strip(),
                    "source_file": filename
                })
        else:
            chunk_id = f"operators_{base_idx:04d}_{i+1:02d}"
            chunks.append({
                "chunk_id": chunk_id,
                "section": sec_name,
                "content": sec_content.strip(),
                "source_file": filename
            })
    return chunks

def _merge_tiny_sections(sections: List[tuple], min_len: int = 500) -> List[tuple]:
    """Merge sections < min_len into the smaller of their prev/next neighbors."""
    section_data = list(sections)
    total = len(section_data)
    merge_into = {}

    for i in range(total):
        sec_name, sec_content = section_data[i]
        if sec_content.strip() and len(sec_content.strip()) < min_len:
            prev_i = next_i = None
            for j in range(i - 1, -1, -1):
                if section_data[j][1].strip():
                    prev_i = j
                    break
            for j in range(i + 1, total):
                if section_data[j][1].strip():
                    next_i = j
                    break
            if prev_i is not None and next_i is not None:
                pl = len(section_data[prev_i][1].strip())
                nl = len(section_data[next_i][1].strip())
                target_i = prev_i if pl <= nl else next_i
            elif prev_i is not None:
                target_i = prev_i
            elif next_i is not None:
                target_i = next_i
            else:
                target_i = None
            if target_i is not None:
                merge_into[i] = target_i

    merged = list(section_data)
    for i, target_i in sorted(merge_into.items(), reverse=True):
        if merged[i] is None or merged[target_i] is None:
            continue
        tiny_name, tiny_content = merged[i]
        merged[i] = None
        neighbor_name, neighbor_content = merged[target_i]
        merged[target_i] = (neighbor_name, (neighbor_content + "\n\n" + tiny_content).strip())

    return [s for s in merged if s is not None]

def _extract_h1_title(sec_content: str) -> tuple:
    """If sec_content starts with an H1 '# Title', strip it and return (title, remaining)."""
    lines = sec_content.split('\n')
    for idx, line in enumerate(lines):
        if re.match(r'^#\s+.+$', line.strip()):
            h1 = line.strip()[1:].strip()
            remaining = '\n'.join(lines[idx+1:]).strip()
            return h1, remaining
    return None, sec_content

def _promote_h1_title(sections: List[tuple]) -> List[tuple]:
    """If the first section's content starts with an H1 '# Title', use H1 as section name."""
    if not sections:
        return sections
    sec_name, sec_content = sections[0]
    h1_title, remaining = _extract_h1_title(sec_content)
    if h1_title:
        sections = [(h1_title, remaining)] + list(sections[1:])
    return sections

def chunk_story_file(content: str, filename: str, base_idx: int) -> List[Dict]:
    """Split story md by ## sections."""
    sections = split_by_sections(content)
    sections = _merge_tiny_sections(sections, min_len=500)
    sections = _promote_h1_title(sections)

    chunks = []
    for i, (sec_name, sec_content) in enumerate(sections):
        if not sec_content.strip():
            continue
        if len(sec_content) > 1500:
            sub_chunks = split_long_text(sec_content, max_chars=1500)
            for j, sub in enumerate(sub_chunks):
                chunk_id = f"stories_{base_idx:04d}_{i+1:02d}_{j+1:02d}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "section": sec_name,
                    "content": sub.strip(),
                    "source_file": filename
                })
        else:
            chunk_id = f"stories_{base_idx:04d}_{i+1:02d}"
            chunks.append({
                "chunk_id": chunk_id,
                "section": sec_name,
                "content": sec_content.strip(),
                "source_file": filename
            })
    return chunks

def chunk_json_record(obj: Dict, collection: str, idx: int) -> Dict:
    """Convert a JSON record to a text chunk."""
    from backend.data.loader import json_to_text
    name = obj.get("名称", obj.get("干员名", obj.get("敌人索引", f"{collection}_record")))
    return {
        "chunk_id": f"{collection}_{idx:04d}",
        "section": name,
        "content": json_to_text(obj),
        "source_file": f"{collection}.json"
    }

def chunk_memes(memes_data: Dict) -> List[Dict]:
    """Chunk memes by category. Uses actual keys present in memes_data."""
    chunks = []

    cat_names = {
        'six_star_nicknames': '六星绰号',
        'five_star_nicknames': '五星绰号',
        'four_star_nicknames': '四星绰号',
        'three_star_nicknames': '三星绰号',
        'game_terms': '游戏术语',
        'story_memes': '剧情梗',
        'gacha_memes': '抽卡梗',
        'base_memes': '基建梗',
        'event_memes': '活动梗',
        'roguelike_memes': '肉鸽梗',
        'special_memes': '特殊梗',
        'community_memes': '社区梗',
        'operator_groups': '干员组合',
    }

    META_KEYS = {'dataset_name', 'version', 'last_updated', 'description', 'metadata'}

    def format_item(cat: str, item: Dict) -> str:
        """Format a single meme item based on its category's field names."""
        if cat == 'game_terms':
            term = item.get("term", "") or ""
            meaning = item.get("meaning", "") or ""
            return f"## {term}: {meaning}"
        elif cat in ('gacha_memes', 'base_memes', 'event_memes'):
            meme = item.get("meme", "") or ""
            meaning = item.get("meaning", "") or item.get("origin", "") or ""
            return f"## {meme}: {meaning}"
        elif cat == 'special_memes':
            meme = item.get("meme", "") or ""
            members = item.get("members", [])
            origin = item.get("origin", "") or ""
            s = f"## {meme}"
            if members:
                s += f"（成员：{', '.join(members)}）"
            if origin:
                s += f"\n来源: {origin}"
            return s
        elif cat == 'operator_groups':
            group = item.get("group_name", "") or ""
            members = item.get("members", [])
            origin = item.get("origin", "") or ""
            s = f"## {group}"
            if members:
                s += f"（成员：{', '.join(members)}）"
            if origin:
                s += f"\n来源: {origin}"
            return s
        else:
            name = item.get("operator_name", item.get("term_name", "")) or ""
            nicknames = item.get("nicknames", item.get("description", []))
            origin = item.get("origin", "") or ""
            s = f"## {name}: {', '.join(nicknames) if isinstance(nicknames, list) else nicknames}"
            if origin:
                s += f"\n来源: {origin}"
            return s

    for cat, cat_data in memes_data.items():
        if cat in META_KEYS or not isinstance(cat_data, list):
            continue

        cat_chinese = cat_names.get(cat, cat)
        lines = [f"### {cat_chinese}"]

        for item in cat_data:
            if isinstance(item, dict):
                formatted = format_item(cat, item)
                if formatted.strip():
                    lines.append(formatted)
            else:
                lines.append(str(item))

        content = "\n".join(lines)
        chunks.append({
            "chunk_id": f"memes_{len(chunks)+1:03d}",
            "section": cat_chinese,
            "content": content,
            "source_file": "arknights_memes_dataset.json"
        })

    return chunks

def chunk_operators_summary(summary: Dict) -> List[Dict]:
    """operators_summary is small (~1.5KB), return as 1 chunk."""
    lines = []
    for key, value in summary.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"- {k}: {v}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"- {', '.join(f'{kk}: {vv}' for kk, vv in item.items())}")
                else:
                    lines.append(f"- {item}")
        else:
            lines.append(f"{key}: {value}")
    return [{
        "chunk_id": "operators_summary_001",
        "section": "干员统计总览",
        "content": "\n".join(lines),
        "source_file": "operators_summary.json"
    }]

def chunk_all_data(limit: int = None):
    """Main orchestrator: chunk all sources and write to chunks/ directory.

    Args:
        limit: if set, only chunk the first N files from operators/ and stories/
               (use for preview before full run).
    """
    chunks_dir = CHUNKS_DIR
    if chunks_dir.exists():
        for sub in ["operators", "stories", "knowledge"]:
            sub_path = chunks_dir / sub
            if sub_path.exists():
                shutil.rmtree(sub_path, ignore_errors=True)
            sub_path.mkdir(parents=True)
    else:
        chunks_dir.mkdir(parents=True)
        for sub in ["operators", "stories", "knowledge"]:
            (chunks_dir / sub).mkdir(parents=True)

    ops_files = sorted((DATA_DIR / 'operators').glob('*.md'))
    if limit is not None:
        ops_files = ops_files[:limit]
    for file_idx, filepath in enumerate(ops_files):
        content = load_md_file(str(filepath))
        chunks = chunk_operators_file(content, filepath.name, file_idx + 1)
        for chunk in chunks:
            out_path = chunks_dir / "operators" / f"{chunk['chunk_id']}.md"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"# {chunk['section']}\n\n{chunk['content']}")

    story_files = sorted((DATA_DIR / 'stories').glob('*.md'))
    if limit is not None:
        story_files = story_files[:limit]
    for file_idx, filepath in enumerate(story_files):
        content = load_md_file(str(filepath))
        chunks = chunk_story_file(content, filepath.name, file_idx + 1)
        for chunk in chunks:
            out_path = chunks_dir / "stories" / f"{chunk['chunk_id']}.md"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"# {chunk['section']}\n\n{chunk['content']}")

    ops = load_all_operators(str(DATA_DIR / 'all_operators.json'))
    for idx, op in enumerate(ops, 1):
        chunk = chunk_json_record(op, 'operators_json', idx)
        out_path = chunks_dir / "knowledge" / f"{chunk['chunk_id']}.txt"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(chunk['content'])

    enemies = load_all_enemies(str(DATA_DIR / 'all_enemies.json'))
    for idx, enemy in enumerate(enemies, 1):
        chunk = chunk_json_record(enemy, 'enemies_json', idx)
        out_path = chunks_dir / "knowledge" / f"{chunk['chunk_id']}.txt"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(chunk['content'])

    gameplay_content = load_gameplay(str(DATA_DIR / 'gameplay.md'))
    gameplay_parts = gameplay_content.split("***")
    GAMEPLAY_SKIP = {'gameplay_0001', 'gameplay_0019'}
    for i, part in enumerate(gameplay_parts):
        part = part.strip()
        if not part:
            continue
        title_match = re.search(r'^##\s+(.+?)$', part, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f"游戏玩法{i+1}"
        chunk_id = f"gameplay_{i+1:04d}"
        if chunk_id not in GAMEPLAY_SKIP:
            out_path = chunks_dir / "knowledge" / f"{chunk_id}.md"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n\n{part}")

    ops_sum_path = DATA_DIR / 'operators_summary.json'
    if ops_sum_path.exists():
        ops_sum = load_operators_summary(str(ops_sum_path))
        summary_chunks = chunk_operators_summary(ops_sum)
        for chunk in summary_chunks:
            out_path = chunks_dir / "knowledge" / f"{chunk['chunk_id']}.txt"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(chunk['content'])

    memes_data = load_memes(str(DATA_DIR / 'arknights_memes_dataset.json'))
    memes_chunks = chunk_memes(memes_data)
    for chunk in memes_chunks:
        out_path = chunks_dir / "knowledge" / f"{chunk['chunk_id']}.txt"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(chunk['content'])

    char_sum_path = DATA_DIR / "char_summary.md"
    if char_sum_path.exists():
        char_sum_content = load_md_file(str(char_sum_path))
        char_sections = split_by_sections(char_sum_content)
        for i, (sec_name, sec_content) in enumerate(char_sections):
            if not sec_content.strip():
                continue
            out_path = chunks_dir / "knowledge" / f"char_summary_{i+1:03d}.txt"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"# {sec_name}\n\n{sec_content.strip()}")

    story_sum_path = DATA_DIR / "story_summary.md"
    if story_sum_path.exists():
        story_sum_content = load_md_file(str(story_sum_path))
        story_sections = split_by_sections(story_sum_content)
        for i, (sec_name, sec_content) in enumerate(story_sections):
            if not sec_content.strip():
                continue
            out_path = chunks_dir / "knowledge" / f"story_summary_{i+1:03d}.txt"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"# {sec_name}\n\n{sec_content.strip()}")

    print(f"Chunking complete!")
    print(f"  operators: {len(list((chunks_dir / 'operators').glob('*')))} files")
    print(f"  stories: {len(list((chunks_dir / 'stories').glob('*')))} files")
    print(f"  knowledge: {len(list((chunks_dir / 'knowledge').glob('*')))} files")

if __name__ == "__main__":
    chunk_all_data()
