"""
Unit tests for backend/agent/skills.py
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agent.skills import (
    _parse_frontmatter,
    scan_skills,
    build_skills_summary,
    read_skill_content,
    get_skills_registry,
)


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = "---\nname: test\n---\nBody content here"
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "test"
        assert body.strip() == "Body content here"

    def test_no_frontmatter(self):
        content = "Just body content"
        meta, body = _parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_multiline_frontmatter(self):
        content = "---\nname: pptx\ndescription: \"Create slides\"\n---\n# PPTX Skill"
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "pptx"
        assert meta["description"] == "Create slides"
        assert "# PPTX Skill" in body


class TestScanSkills:
    def _make_skill(self, base_dir: Path, name: str, desc: str = "") -> Path:
        """Helper: create a skill directory with SKILL.md."""
        skill_dir = base_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        frontmatter = f"---\nname: {name}\ndescription: \"{desc}\"\n---\n\n# {name}\nContent for {name}"
        (skill_dir / "SKILL.md").write_text(frontmatter, encoding="utf-8")
        return skill_dir

    def test_scan_flat_skills(self, tmp_path):
        """Test scanning skills in a flat directory structure."""
        self._make_skill(tmp_path, "pptx", "PPT skill")
        self._make_skill(tmp_path, "docx", "DOC skill")

        skills = scan_skills(tmp_path)
        assert len(skills) == 2
        names = {s["name"] for s in skills}
        assert names == {"pptx", "docx"}

    def test_scan_nested_pack(self, tmp_path):
        """Test scanning skills inside a pack directory (no SKILL.md at pack level)."""
        pack_dir = tmp_path / "superpowers"
        pack_dir.mkdir()
        self._make_skill(pack_dir, "rag_search", "RAG search skill")
        self._make_skill(pack_dir, "doc_analysis", "Doc analysis skill")

        skills = scan_skills(tmp_path)
        assert len(skills) == 2
        names = {s["name"] for s in skills}
        assert names == {"rag_search", "doc_analysis"}

    def test_scan_stops_at_skill_boundary(self, tmp_path):
        """Test that scanning does NOT recurse into a skill's subdirectory."""
        skill_dir = self._make_skill(tmp_path, "pptx", "PPT skill")
        # Create a nested SKILL.md inside the skill — should NOT be picked up
        nested = skill_dir / "internal" / "helper"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text("---\nname: helper\n---\nHelper", encoding="utf-8")

        skills = scan_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0]["name"] == "pptx"

    def test_scan_mixed_structure(self, tmp_path):
        """Test flat skills + nested pack in the same directory."""
        self._make_skill(tmp_path, "xlsx", "Excel skill")
        pack_dir = tmp_path / "office_pack"
        pack_dir.mkdir()
        self._make_skill(pack_dir, "pptx", "PPT skill")
        self._make_skill(pack_dir, "docx", "DOC skill")

        skills = scan_skills(tmp_path)
        assert len(skills) == 3
        names = {s["name"] for s in skills}
        assert names == {"xlsx", "pptx", "docx"}

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning an empty skills directory."""
        skills = scan_skills(tmp_path)
        assert skills == []

    def test_scan_nonexistent_directory(self, tmp_path):
        """Test scanning a directory that doesn't exist."""
        skills = scan_skills(tmp_path / "nonexistent")
        assert skills == []

    def test_scan_ignores_dotfiles(self, tmp_path):
        """Test that directories starting with . are ignored."""
        self._make_skill(tmp_path, "pptx", "PPT skill")
        dot_dir = tmp_path / ".hidden"
        dot_dir.mkdir()
        (dot_dir / "SKILL.md").write_text("---\nname: hidden\n---\nHidden", encoding="utf-8")

        skills = scan_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0]["name"] == "pptx"


class TestBuildSkillsSummary:
    def test_summary_contains_skill_names(self, tmp_path):
        """Test that summary includes all skill names."""
        for name in ["pptx", "docx", "pdf"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: \"{name} skill\"\n---\nContent",
                encoding="utf-8",
            )

        summary = build_skills_summary(scan_skills(tmp_path))
        assert "pptx" in summary
        assert "docx" in summary
        assert "pdf" in summary
        assert "Available Skills" in summary
        assert "read_skill" in summary

    def test_summary_empty(self, tmp_path):
        """Test that summary is empty string when no skills."""
        summary = build_skills_summary(scan_skills(tmp_path))
        assert summary == ""

    def test_summary_truncates_long_description(self, tmp_path):
        """Test that long descriptions are truncated in summary."""
        d = tmp_path / "test"
        d.mkdir()
        long_desc = "A" * 300
        (d / "SKILL.md").write_text(
            f"---\nname: test\ndescription: \"{long_desc}\"\n---\nContent",
            encoding="utf-8",
        )

        summary = build_skills_summary(scan_skills(tmp_path))
        # Should not contain the full 300-char description in the summary line
        assert "..." in summary


class TestReadSkillContent:
    def test_read_by_path(self, tmp_path):
        """Test reading skill content by absolute path."""
        skill_file = tmp_path / "test" / "SKILL.md"
        skill_file.parent.mkdir()
        skill_file.write_text("---\nname: test\n---\nFull content here", encoding="utf-8")

        content = read_skill_content(skill_path=str(skill_file))
        assert content is not None
        assert "Full content here" in content

    def test_read_by_name(self, tmp_path):
        """Test reading skill content by name."""
        for name in ["pptx", "docx"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\n---\nContent for {name}",
                encoding="utf-8",
            )

        skills = scan_skills(tmp_path)
        content = read_skill_content(skill_name="pptx", skills=skills)
        assert content is not None
        assert "Content for pptx" in content

    def test_read_nonexistent_name(self, tmp_path):
        """Test reading a skill that doesn't exist."""
        content = read_skill_content(skill_name="nonexistent", skills=[])
        assert content is None

    def test_read_nonexistent_path(self, tmp_path):
        """Test reading a path that doesn't exist."""
        content = read_skill_content(skill_path=str(tmp_path / "nope.md"))
        assert content is None


class TestGetSkillsRegistry:
    def test_registry_maps_names(self, tmp_path):
        """Test that registry correctly maps names to skill info."""
        for name in ["pptx", "docx"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\n---\nContent",
                encoding="utf-8",
            )

        registry = get_skills_registry(tmp_path)
        assert "pptx" in registry
        assert "docx" in registry
        assert registry["pptx"]["name"] == "pptx"


class TestReadSkillTool:
    @pytest.mark.asyncio
    async def test_read_skill_tool_success(self, tmp_path):
        """Test execute_read_skill tool function."""
        d = tmp_path / "pptx"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: pptx\ndescription: \"PPT skill\"\n---\n# PPTX\nFull guide",
            encoding="utf-8",
        )

        import backend.agent.skills as skills_mod
        # Temporarily override the scan function
        original_dir = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path
            from backend.agent.tool_implementations import execute_read_skill

            result = await execute_read_skill({"skill_name": "pptx"})
            assert "Full guide" in result
        finally:
            skills_mod.SKILLS_DIR = original_dir

    @pytest.mark.asyncio
    async def test_read_skill_tool_not_found(self, tmp_path):
        """Test execute_read_skill with non-existent skill."""
        import backend.agent.skills as skills_mod
        original_dir = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path
            from backend.agent.tool_implementations import execute_read_skill

            result = await execute_read_skill({"skill_name": "nonexistent"})
            assert "未找到" in result
        finally:
            skills_mod.SKILLS_DIR = original_dir

    @pytest.mark.asyncio
    async def test_read_skill_tool_missing_param(self, tmp_path):
        """Test execute_read_skill with missing parameter."""
        from backend.agent.tool_implementations import execute_read_skill

        result = await execute_read_skill({})
        assert "错误" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
