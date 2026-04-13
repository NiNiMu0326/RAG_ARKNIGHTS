"""
Skill discovery and loading for AgenticRAG.

Directory structure:
    skills/
      docx/
        SKILL.md          <- one Skill
      pdf/
        SKILL.md          <- one Skill
      superpowers/        <- skill pack (no SKILL.md here)
        rag_search/
          SKILL.md        <- one Skill (found by recursion)

Scan rules:
  - If a directory has SKILL.md, load it and do NOT recurse into subdirectories.
  - If a directory has no SKILL.md, recurse into its subdirectories.
"""

import os
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default skills directory
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"

# Number of lines to include in the summary (from after frontmatter)
SUMMARY_MAX_LINES = 5


def _parse_frontmatter(content: str) -> tuple:
    """Parse YAML frontmatter from a SKILL.md file.

    Returns:
        (metadata_dict, body_str)
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        metadata = {}
    body = content[match.end():]
    return metadata, body


def scan_skills(skills_dir: Path = None) -> List[Dict]:
    """Scan the skills directory and return a list of skill info dicts.

    Each dict has:
      - name: skill name from frontmatter
      - description: description from frontmatter
      - path: absolute path to the SKILL.md file
      - relative_path: path relative to skills_dir

    Args:
        skills_dir: Root directory to scan. Defaults to project skills/.
    """
    skills_dir = skills_dir or SKILLS_DIR
    if not skills_dir.is_dir():
        logger.warning(f"Skills directory not found: {skills_dir}")
        return []

    skills = []
    _scan_recursive(skills_dir, skills_dir, skills)
    logger.info(f"Found {len(skills)} skill(s) in {skills_dir}")
    return skills


def _scan_recursive(current_dir: Path, root_dir: Path, skills: List[Dict]):
    """Recursively scan for SKILL.md files.

    If SKILL.md exists in current_dir, load it and stop recursing this branch.
    Otherwise, recurse into subdirectories.
    """
    skill_file = current_dir / "SKILL.md"
    if skill_file.is_file():
        try:
            content = skill_file.read_text(encoding="utf-8")
            metadata, _ = _parse_frontmatter(content)
            relative_path = skill_file.relative_to(root_dir)
            skills.append({
                "name": metadata.get("name", skill_file.parent.name),
                "description": metadata.get("description", ""),
                "path": str(skill_file.resolve()),
                "relative_path": str(relative_path),
            })
            # Do NOT recurse further — this directory is a skill
        except Exception as e:
            logger.error(f"Failed to read {skill_file}: {e}")
    else:
        # No SKILL.md here — recurse into subdirectories
        try:
            for child in sorted(current_dir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    _scan_recursive(child, root_dir, skills)
        except PermissionError:
            pass


def build_skills_summary(skills: List[Dict] = None) -> str:
    """Build a summary string for all skills to inject into System Prompt.

    Format:
        ## Available Skills
        - **pptx**: Use this skill any time a .pptx file is involved...
        - **docx**: Use this skill whenever the user wants to create...

    Args:
        skills: List of skill info dicts. If None, scans the skills directory.
    """
    if skills is None:
        skills = scan_skills()

    if not skills:
        return ""

    lines = ["## Available Skills", ""]
    for skill in skills:
        name = skill["name"]
        desc = skill["description"]
        if desc:
            # Truncate long descriptions for system prompt
            if len(desc) > 150:
                desc = desc[:147] + "..."
            lines.append(f"- **{name}**: {desc}")
        else:
            lines.append(f"- **{name}**: (no description)")

    lines.append("")
    lines.append("当你判断需要使用某个 Skill 时，使用 `read_skill` 工具读取该 Skill 的完整指令内容，然后严格按照指令执行。")
    lines.append("")

    return "\n".join(lines)


def read_skill_content(skill_path: str = None, skill_name: str = None, skills: List[Dict] = None) -> Optional[str]:
    """Read the full content of a specific skill's SKILL.md.

    Args:
        skill_path: Absolute path to SKILL.md.
        skill_name: Skill name to look up (used if skill_path is None).
        skills: List of skill info dicts (used if skill_path is None).

    Returns:
        Full content string, or None if not found.
    """
    if skill_path:
        path = Path(skill_path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    # Look up by name
    if skill_name and skills:
        for skill in skills:
            if skill["name"] == skill_name:
                path = Path(skill["path"])
                if path.is_file():
                    return path.read_text(encoding="utf-8")
        return None

    return None


def get_skills_registry(skills_dir: Path = None) -> Dict[str, Dict]:
    """Build a name -> skill info mapping.

    Returns:
        Dict mapping skill name to skill info dict.
    """
    skills = scan_skills(skills_dir)
    return {s["name"]: s for s in skills}
