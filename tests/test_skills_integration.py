"""
Integration tests for Skills + Agent pipeline.
Tests that skills are loaded into system prompt and read_skill tool works in agent loop.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSkillsIntegration:
    def test_build_messages_includes_skills_summary(self):
        """Test that build_messages appends skills summary to system prompt."""
        from backend.agent.prompts import build_messages
        from backend.agent.sessions import Session, SessionManager

        sm = SessionManager(max_sessions=10, ttl_seconds=60)
        sid = sm.create_session()

        messages = build_messages(sm.get_session(sid))
        assert len(messages) >= 1
        system_msg = messages[0]
        assert system_msg["role"] == "system"

        content = system_msg["content"]
        # System prompt should include the base prompt
        assert "明日方舟" in content

        # Should include skills summary since skills/ directory has SKILL.md files
        assert "Available Skills" in content
        # Check at least one of the actual skills
        assert any(name in content for name in ["pptx", "docx", "pdf", "xlsx"])
        # Should mention read_skill tool
        assert "read_skill" in content

    def test_read_skill_tool_integration(self):
        """Test read_skill tool can actually read the real pptx skill."""
        from backend.agent.skills import scan_skills, read_skill_content

        skills = scan_skills()
        names = [s["name"] for s in skills]
        print(f"Found skills: {names}")

        assert len(skills) >= 4, f"Expected at least 4 skills, got {len(skills)}: {names}"

        # Read the pptx skill
        pptx_skills = [s for s in skills if s["name"] == "pptx"]
        assert len(pptx_skills) == 1, "pptx skill not found"

        content = read_skill_content(skill_path=pptx_skills[0]["path"])
        assert content is not None
        assert len(content) > 100, f"pptx skill content too short: {len(content)} chars"
        assert "pptxgenjs" in content.lower() or "pptx" in content.lower()

    def test_all_real_skills_readable(self):
        """Test all 4 real skills can be read by name."""
        from backend.agent.skills import scan_skills, read_skill_content

        skills = scan_skills()
        registry = {s["name"]: s for s in skills}

        for expected_name in ["pptx", "docx", "pdf", "xlsx"]:
            assert expected_name in registry, f"Skill '{expected_name}' not found"
            content = read_skill_content(skill_name=expected_name, skills=skills)
            assert content is not None, f"Could not read skill '{expected_name}'"
            assert len(content) > 50, f"Skill '{expected_name}' content too short"

    def test_tool_registry_has_read_skill(self):
        """Test that read_skill is registered in the tool registry."""
        from backend.agent.tools import get_tool_registry

        registry = get_tool_registry()
        schemas = registry.get_schemas()
        tool_names = [s["function"]["name"] for s in schemas]

        assert "read_skill" in tool_names, f"read_skill not in tools: {tool_names}"

    def test_skills_summary_format(self):
        """Test that the skills summary has the expected format."""
        from backend.agent.skills import build_skills_summary, scan_skills

        summary = build_skills_summary()
        lines = summary.strip().split("\n")

        # First line should be the header
        assert lines[0] == "## Available Skills"
        # Each skill should be a bullet point
        bullet_lines = [l for l in lines if l.startswith("- **")]
        assert len(bullet_lines) >= 4, f"Expected >= 4 skill bullets, got {len(bullet_lines)}"

        # Each bullet should have a name in bold
        for line in bullet_lines:
            assert "**" in line, f"Bullet line missing bold marker: {line}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
