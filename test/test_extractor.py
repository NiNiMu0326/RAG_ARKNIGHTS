"""
Tests for backend.rag.graphrag.extractor: helper functions.
Usage: cd test && python -m pytest test_extractor.py -v
"""
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag.graphrag.extractor import (
    _extract_key_sections,
    _parse_key_persons,
    _build_prompt,
)


# ============================================================
# _extract_key_sections
# ============================================================

class TestExtractKeySections:
    """Test extraction of 关键人物 and 角色剧情概括 from markdown content."""

    def test_extracts_both_sections(self):
        content = """## 基本信息
一些基础信息

## 关键人物
关键人物：银灰;初雪;崖心

## 角色剧情概括
银灰是喀兰贸易的领袖，与妹妹初雪和崖心有关联。

## 其他信息
其他"""
        key_section, summary_section = _extract_key_sections(content)
        assert "银灰" in key_section
        assert "初雪" in key_section
        assert "崖心" in key_section
        assert "喀兰贸易" in summary_section

    def test_no_key_persons_section(self):
        content = """## 基本信息
一些内容

## 角色剧情概括
剧情概括内容
"""
        key_section, summary_section = _extract_key_sections(content)
        assert key_section == ""
        assert "剧情概括内容" in summary_section

    def test_no_summary_section(self):
        content = """## 基本信息
内容

## 关键人物
关键人物：银灰
"""
        key_section, summary_section = _extract_key_sections(content)
        assert "银灰" in key_section
        assert summary_section == ""

    def test_empty_content(self):
        key_section, summary_section = _extract_key_sections("")
        assert key_section == ""
        assert summary_section == ""

    def test_sections_not_present(self):
        content = "## 其他内容\n没有关键人物和剧情概括"
        key_section, summary_section = _extract_key_sections(content)
        assert key_section == ""
        assert summary_section == ""

    def test_stops_at_next_heading(self):
        content = """## 关键人物
关键人物：银灰

## 下一个章节
这个不应该出现在关键人物中"""
        key_section, _ = _extract_key_sections(content)
        assert "银灰" in key_section
        assert "下一个章节" not in key_section
        assert "不应该出现" not in key_section

    def test_alternative_summary_heading(self):
        """角色剧情概述 (alternative heading) should also be detected."""
        content = """## 角色剧情概述
剧情摘要内容
"""
        _, summary_section = _extract_key_sections(content)
        assert "剧情摘要内容" in summary_section


# ============================================================
# _parse_key_persons
# ============================================================

class TestParseKeyPersons:
    """Test parsing of key persons from the extracted section."""

    def test_parses_semicolon_separated(self):
        key_section = "关键人物：银灰;初雪;崖心"
        result = _parse_key_persons(key_section)
        assert result == ["银灰", "初雪", "崖心"]

    def test_removes_prefix(self):
        key_section = "关键人物：银灰"
        result = _parse_key_persons(key_section)
        assert result == ["银灰"]

    def test_colon_prefix(self):
        key_section = "关键人物:银灰"
        result = _parse_key_persons(key_section)
        assert result == ["银灰"]

    def test_strips_whitespace(self):
        key_section = "关键人物： 银灰 ; 初雪 ; 崖心 "
        result = _parse_key_persons(key_section)
        assert result == ["银灰", "初雪", "崖心"]

    def test_removes_parenthetical_content(self):
        key_section = "关键人物：银灰(恩希欧迪斯);初雪(恩雅)"
        result = _parse_key_persons(key_section)
        assert result == ["银灰", "初雪"]

    def test_filters_single_character_names(self):
        key_section = "关键人物：A;银灰"
        result = _parse_key_persons(key_section)
        assert "A" not in result
        assert "银灰" in result

    def test_filters_names_with_de(self):
        """Names containing 的 should be filtered out (e.g. 能天使的姐姐)."""
        key_section = "关键人物：能天使的姐姐;银灰"
        result = _parse_key_persons(key_section)
        assert "能天使的姐姐" not in result
        assert "银灰" in result

    def test_filters_long_names(self):
        """Names longer than 15 chars should be filtered."""
        key_section = "关键人物：这是一个非常长的描述超过十五个字;银灰"
        result = _parse_key_persons(key_section)
        assert "银灰" in result
        long_names = [p for p in result if len(p) > 15]
        assert len(long_names) == 0

    def test_filters_descriptive_prefixes(self):
        """Prefixes like 可疑的, 最后的 should filter out the name."""
        key_section = "关键人物：可疑的术士;最后的骑士;沉默的守卫;银灰"
        result = _parse_key_persons(key_section)
        assert "可疑的术士" not in result
        assert "最后的骑士" not in result
        assert "沉默的守卫" not in result
        assert "银灰" in result

    def test_filters_special_characters(self):
        """Names with brackets or quotes should be filtered."""
        key_section = "关键人物：[测试];银灰"
        result = _parse_key_persons(key_section)
        assert "[测试]" not in result  # brackets filtered
        assert "银灰" in result

    def test_empty_section(self):
        result = _parse_key_persons("")
        assert result == []

    def test_strips_content_after_colon(self):
        """Extra text after colon prefix — function doesn't strip trailing content per-person."""
        key_section = "关键人物：银灰;初雪 其他文本"
        result = _parse_key_persons(key_section)
        assert "银灰" in result
        # The second item includes the trailing text as part of the name
        # since parse_key_persons only strips at the section level
        assert any("初雪" in p for p in result)


# ============================================================
# _build_prompt
# ============================================================

class TestBuildPrompt:
    """Test prompt construction for entity extraction."""

    def test_basic_prompt_structure(self):
        prompt = _build_prompt("测试文档内容", [], [])
        assert "测试文档内容" in prompt
        assert "实体类型" in prompt
        assert "关系类型" in prompt
        assert "输出格式" in prompt

    def test_includes_known_relation_types(self):
        known_types = ["所属", "朋友", "对立"]
        prompt = _build_prompt("doc content", known_types, [])
        assert '"所属"' in prompt
        assert '"朋友"' in prompt
        assert '"对立"' in prompt

    def test_no_relation_types_message(self):
        prompt = _build_prompt("doc", [], [])
        assert "暂无已知关系类型" in prompt

    def test_includes_known_operators(self):
        ops = ["银灰", "初雪", "崖心"]
        prompt = _build_prompt("doc", [], ops)
        assert "已知干员" in prompt
        assert "银灰" in prompt
        assert "初雪" in prompt
        assert "崖心" in prompt

    def test_known_operators_truncated_at_100(self):
        """When there are more than 100 operators, the list should be truncated."""
        ops = [f"干员{i}" for i in range(150)]
        prompt = _build_prompt("doc", [], ops)
        assert "等共150个干员" in prompt
        # First 100 should be present, 101st should not
        assert "干员0" in prompt
        assert "干员99" in prompt
        assert "干员100" not in prompt

    def test_no_operators_message(self):
        prompt = _build_prompt("doc", [], [])
        # The prompt template contains static text about known operators
        # but when operators list is empty, the {operators_hint} is empty string
        assert "已知干员（这些是" not in prompt  # Dynamic hint should be absent
        assert "{operators_hint}" not in prompt  # Variable should be substituted

    def test_direct_json_output_instruction(self):
        prompt = _build_prompt("doc", [], [])
        assert "直接输出JSON对象" in prompt
