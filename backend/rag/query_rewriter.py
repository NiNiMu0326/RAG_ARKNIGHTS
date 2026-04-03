import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from typing import List, Dict, Optional
from backend.api.siliconflow import SiliconFlowClient

ALIAS_MAP = {
    "银老板": "银灰",
    "小羊": "艾雅法拉",
    "火山羊": "艾雅法拉",
    "龙": "伊芙利特",
    "小火龙": "伊芙利特",
    "德狗": "德克萨斯",
    "德克萨斯": "德克萨斯",
    "龙虾": "温蒂",
    "老陈": "陈",
    "陈警司": "陈",
    "假日威龙陈": "陈",
    "小羊": "艾雅法拉",
    "羊": "艾雅法拉",
    "奶羊": "艾雅法拉",
    "塞雷娅": "塞雷娅",
    "塞妈": "塞雷娅",
    "42": "史尔特尔",
    "辣辣": "史尔特尔",
    "迷迭香": "迷迭香",
    "百嘉": "谜图",
}

REWRITE_PROMPT = """你是一个查询改写专家。请将用户的问题改写成检索 query。

## 任务
1. **别名扩展**：将游戏内别名/外号扩展为正式干员名
2. **代词消解**：根据对话历史，将代词替换为具体名称
3. **查询分解**（重点）：如果问题涉及多个实体/多个方面，必须拆分为多个独立查询

## 别名参考
银老板→银灰, 小羊/火山羊→艾雅法拉, 小火龙/龙→伊芙利特, 老陈/陈警司→陈, 42→史尔特尔, 塞妈→塞雷娅 等

## 输出格式
- 单个查询：直接输出 query 文本
- 多个查询：每行一个查询，query 之间用 | 分隔，不要有其他符号

## 示例
用户: 银灰和陈晖仲是什么关系？
输出: 银灰 关系
| 陈晖仲 关系

用户: 银灰是谁？她和哪些干员有合作？
历史: 无
输出: 银灰 身份 背景
| 银灰 合作 干员

用户: 银老板和塞雷娅有什么关系？
输出: 银灰 塞雷娅 关系

用户: 陈晖仲是六星狙击吗？
输出: 陈晖仲 六星 狙击

## 用户问题
{query}

## 对话历史
{history}

## 改写后的 query
"""

class QueryRewriter:
    def __init__(self, api_key: str = None):
        self.client = SiliconFlowClient(api_key)

    def _expand_aliases(self, text: str) -> str:
        """Expand known aliases in text."""
        for alias, name in ALIAS_MAP.items():
            if alias in text:
                text = text.replace(alias, name)
        return text

    def _resolve_history_references(self, text: str, history: List[Dict]) -> str:
        """Try to resolve pronouns using conversation history (simple approach)."""
        # If no history, return as-is
        if not history:
            return text

        # Find the last mentioned operator in history
        last_operator = None
        for msg in reversed(history):
            content = msg.get("content", "")
            for alias, name in ALIAS_MAP.items():
                if alias in content or name in content:
                    last_operator = name
                    break
            if last_operator:
                break

        # Replace common pronouns with last operator
        if last_operator:
            pronouns = ["她", "他", "它", "这个干员", "这位干员"]
            for p in pronouns:
                if p in text:
                    text = text.replace(p, last_operator)

        return text

    def rewrite(self, query: str, history: List[Dict] = None) -> List[str]:
        """Rewrite a user query. Returns a list of one or more sub-queries."""
        history = history or []

        # First, expand known aliases
        query = self._expand_aliases(query)

        # Try to resolve history references
        query = self._resolve_history_references(query, history)

        # Build history text for prompt
        history_text = ""
        if history:
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-3:]])

        # Call LLM for final rewrite
        prompt = REWRITE_PROMPT.format(query=query, history=history_text or "无")

        try:
            response = self.client.chat([
                {"role": "system", "content": "你是一个查询改写专家。直接输出改写后的 query，不要解释。"},
                {"role": "user", "content": prompt}
            ])
            raw = response.strip()

            # Parse: if contains |, split into multiple sub-queries
            if '|' in raw:
                queries = [q.strip() for q in raw.split('|') if q.strip()]
                return queries if queries else [query]
            else:
                return [raw] if raw else [query]

        except Exception as e:
            # Fallback to simple expanded query
            return [query]