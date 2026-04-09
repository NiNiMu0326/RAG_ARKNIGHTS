import sys
import time
from pathlib import Path
import functools
import json
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Optional, Tuple
from backend.api.siliconflow import SiliconFlowClient

# 全局缓存字典（用于QueryRewriter的LLM结果缓存）
# 格式: {cache_key: (timestamp, result)}
_rewrite_cache: Dict[str, Tuple[float, Dict]] = {}
_REWRITE_CACHE_TTL = 18000  # 5 hours
_REWRITE_CACHE_MAX_SIZE = 200

def clear_rewrite_cache():
    """清空QueryRewriter的LLM结果缓存。
    当文档索引重建时需要调用此函数。
    """
    global _rewrite_cache
    _rewrite_cache.clear()

def _get_cached_rewrite(cache_key: str) -> Optional[Dict]:
    """获取缓存的改写结果，如果过期则返回 None"""
    if cache_key in _rewrite_cache:
        timestamp, result = _rewrite_cache[cache_key]
        if time.time() - timestamp < _REWRITE_CACHE_TTL:
            return result
        else:
            del _rewrite_cache[cache_key]
    return None

def _set_cached_rewrite(cache_key: str, result: Dict) -> None:
    """设置缓存的改写结果"""
    if len(_rewrite_cache) >= _REWRITE_CACHE_MAX_SIZE:
        # 移除最老的条目
        oldest_key = min(_rewrite_cache.keys(), key=lambda k: _rewrite_cache[k][0])
        del _rewrite_cache[oldest_key]
    _rewrite_cache[cache_key] = (time.time(), result)

ALIAS_MAP = {
    "银老板": "银灰",
    "小羊": "艾雅法拉",
    "火山羊": "艾雅法拉",
    "龙": "伊芙利特",
    "小火龙": "伊芙利特",
    "德狗": "德克萨斯",
    "龙虾": "温蒂",
    "老陈": "陈",
    "陈警司": "陈",
    "假日威龙陈": "陈",
    "羊": "艾雅法拉",
    "奶羊": "艾雅法拉",
    "塞妈": "塞雷娅",
    "42": "史尔特尔",
    "辣辣": "史尔特尔",
    "迷迭香": "迷迭香",
    "百嘉": "谜图",
}


class QueryRewriter:
    def __init__(self, api_key: str = None):
        # Use SiliconFlow Qwen for LLM chat (fast and accurate)
        self.client = SiliconFlowClient(api_key)
        self.llm_model = "Qwen/Qwen2.5-7B-Instruct"

    def _expand_aliases(self, text: str) -> str:
        """Expand known aliases in text.

        Uses longest-match-first to avoid partial replacements.
        """
        # Sort by length descending to replace longer aliases first
        sorted_aliases = sorted(ALIAS_MAP.items(), key=lambda x: len(x[0]), reverse=True)
        for alias, name in sorted_aliases:
            if alias in text:
                text = text.replace(alias, name)
        return text

    def _resolve_history_references(self, text: str, history: List[Dict]) -> str:
        """Try to resolve pronouns using conversation history (simple approach)."""
        if not history:
            return text

        last_operator = None
        for msg in reversed(history):
            content = msg.get("content", "")
            for alias, name in ALIAS_MAP.items():
                if alias in content or name in content:
                    last_operator = name
                    break
            if last_operator:
                break

        if last_operator:
            pronouns = ["她", "他", "它", "这个干员", "这位干员"]
            for p in pronouns:
                if p in text:
                    text = text.replace(p, last_operator)

        return text

    def _contains_pronouns(self, text: str) -> bool:
        """Check if text contains pronouns that need semantic understanding."""
        pronouns = ['他', '她', '它']
        return any(p in text for p in pronouns)

    def _rewrite_with_llm(self, query: str, history: List[Dict] = None) -> Dict:
        """Rewrite query using LLM (Qwen)."""
        global _rewrite_cache

        # Build history text
        history_text = ""
        if history:
            recent = history[-5:]
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

        prompt = f"""你是一个明日方舟RAG查询改写助手。

## 任务
1. 判断是否需要检索知识库（需要：干员信息/剧情/攻略等；不需要：闲聊/问候/自我回答等）
2. 如果需要检索，将问题改写为简短的关键词组合
3. 如果不需要检索，直接生成闲聊回复

## 查询改写示例
- "银灰技能" → ["银灰 技能"]
- "维什戴尔和史尔特尔关系" → ["维什戴尔 史尔特尔 关系"]
- "维什戴尔和迷迭香的技能分别是什么" → ["维什戴尔 技能", "迷迭香 技能"]（复杂查询要拆成多个简单独立的查询）
- "银灰和初雪的背景故事" → ["银灰 背景", "初雪 背景"]
- "能天使与德克萨斯的获取方式" → ["能天使 获取", "德克萨斯 获取"]
- "维什戴尔的技能和天赋是什么" → ["维什戴尔 技能", "维什戴尔 天赋"]（同一干员多属性也要拆分）
- "她的别名是什么" → ["她 别名"]（无历史时保留代词）
- "她的背景故事" + 历史"维什戴尔" → needs_retrieval=true, queries=["维什戴尔 背景"]（有历史时根据上文替换代词）
- "银灰精英化材料" → ["银灰 精英材料"]
- "银灰声优" → ["银灰 声优"]（声优/CV/配音需要检索）
- "银灰立绘" → ["银灰 立绘"]（立绘/皮肤需要检索）
- "银灰画师" → ["银灰 画师"]（画师/人设需要检索）
- "银灰阵营" → ["银灰 阵营"]（阵营/势力需要检索）
- "继续说" + 历史"银灰技能" → needs_retrieval=true, queries=["银灰 技能"]（接续话题需要检索）
- "还有呢" + 历史"银灰背景" → needs_retrieval=true, queries=["银灰 背景"]（接续话题需要检索）
- "她的别名是什么" + 历史"维什戴尔的技能" → needs_retrieval=true, queries=["维什戴尔 别名"]（有历史时替换代词，仍需检索）
- "什么是源石" → ["源石"]（游戏机制需要检索）

## 判断标准
需要检索：干员属性、技能、天赋、关系、背景、获取方式、攻略、立绘、声优、画师、阵营、公招、寻访等具体信息，以及游戏机制（源石、理智、龙门币、剿灭、芯片等）
不确定是否需要检索时，默认需要检索
不需要检索：问候、自我介绍、天气闲聊、询问看法等

## 输出格式（纯JSON，不要代码块）
{{"needs_retrieval": true或false, "queries": ["关键词1", "关键词2"], "is_relation_query": true或false, "detected_operators": ["干员1", "干员2"], "answer": "非检索时的直接回答"}}

## 对话历史
{history_text if history_text else "无"}

## 用户问题
{query}

## JSON输出
"""
        try:
            response = self.client.chat([
                {"role": "system", "content": "你是一个明日方舟RAG助手，直接输出JSON。"},
                {"role": "user", "content": prompt}
            ], model=self.llm_model)
            raw = response.strip()

            # Strip markdown code fences if present
            if raw.startswith('```'):
                lines = raw.split('\n')
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip().endswith('```'):
                    lines = lines[:-1]
                raw = '\n'.join(lines)
            result = json.loads(raw)

            # Cache successful result
            cache_key = f"{query}|{history_text}"
            _set_cached_rewrite(cache_key, result)

            return result
        except json.JSONDecodeError:
            return {
                "needs_retrieval": True,
                "reason": "JSON解析失败，降级为检索模式",
                "queries": [query],
                "answer": None,
                "is_relation_query": False
            }
        except Exception as e:
            return {
                "needs_retrieval": True,
                "reason": f"错误: {str(e)[:50]}，降级为检索模式",
                "queries": [query],
                "answer": None,
                "is_relation_query": False
            }

    def _strip_punctuation(self, q: str) -> str:
        """去掉末尾的标点符号"""
        while q and q[-1] in '？！。.，、；?,':
            q = q[:-1]
        return q

    def _find_pattern_before(self, q: str, pattern: str) -> str:
        """从后往前找pattern，返回pattern前面的内容。"""
        idx = q.rfind(pattern)
        if idx == -1:
            return None
        before = q[:idx].strip()
        return before if before else None

    def _fast_rule_check(self, query: str) -> Optional[Dict]:
        """Fast rule-based check for common question patterns."""
        q = query.strip()

        # 先去掉末尾标点
        q = self._strip_punctuation(q)

        # 如果一个干员同时查询多个属性（技能、天赋、背景、别名等），fast_rule 无法处理，交给 LLM
        # 例如"维什戴尔的技能和天赋是什么"、"银灰的背景故事与别名"
        attr_keywords = ['技能', '天赋', '背景', '别名', '模组', '精英', '获取', '皮肤', '立绘', '声优', '画师']
        # 统计出现了多少个不同属性关键词
        attrs_found = [a for a in attr_keywords if a in q]
        if len(attrs_found) > 1:
            return None

        # Pattern 1: 技能查询
        for suffix in ["的技能是什么", "技能是什么", "的技能", "技能"]:
            operator = self._find_pattern_before(q, suffix)
            if operator:
                # 如果 operator 包含"和/与/跟"或者包含代词，说明是多干员或代词查询，交给 LLM 处理
                if any(sep in operator for sep in ['和', '与', '跟']):
                    continue
                if self._contains_pronouns(operator):
                    continue
                return {
                    "needs_retrieval": True,
                    "reason": "询问干员技能，需要检索",
                    "queries": [f"{operator} 技能"],
                    "answer": None,
                    "is_relation_query": False
                }

        # Pattern 2: 背景故事查询
        for suffix in ["背景故事是什么", "背景故事"]:
            operator = self._find_pattern_before(q, suffix)
            if operator:
                if any(sep in operator for sep in ['和', '与', '跟']):
                    continue
                if self._contains_pronouns(operator):
                    continue
                return {
                    "needs_retrieval": True,
                    "reason": "询问干员背景故事，需要检索",
                    "queries": [f"{operator} 背景"],
                    "answer": None,
                    "is_relation_query": False
                }

        # Pattern 3: 别名查询
        for suffix in ["别名有什么", "别名"]:
            operator = self._find_pattern_before(q, suffix)
            if operator:
                if any(sep in operator for sep in ['和', '与', '跟']):
                    continue
                if self._contains_pronouns(operator):
                    continue
                return {
                    "needs_retrieval": True,
                    "reason": "询问干员别名，需要检索",
                    "queries": [f"{operator} 别名"],
                    "answer": None,
                    "is_relation_query": False
                }

        # Pattern 4: 关系查询
        for suffix in ["的关系是什么", "的关系"]:
            if q.endswith(suffix):
                for sep in ['和', '与', '跟']:
                    parts = q[:-len(suffix)].split(sep)
                    if len(parts) == 2:
                        op1, op2 = parts[0].strip(), parts[1].strip()
                        if op1 and op2:
                            # 如果任一干员名包含代词，交给 LLM 处理
                            if self._contains_pronouns(op1) or self._contains_pronouns(op2):
                                continue
                            return {
                                "needs_retrieval": True,
                                "reason": "询问干员关系，需要检索",
                                "queries": [f"{op1} {op2} 关系"],
                                "answer": None,
                                "is_relation_query": True,
                                "detected_operators": [op1, op2]
                            }

        # Pattern 5: 故事内容查询
        for suffix in ["故事内容是什么", "故事内容"]:
            story = self._find_pattern_before(q, suffix)
            if story:
                if self._contains_pronouns(story):
                    continue
                return {
                    "needs_retrieval": True,
                    "reason": "询问剧情故事内容，需要检索",
                    "queries": [f"{story} 剧情"],
                    "answer": None,
                    "is_relation_query": False
                }

        # No pattern matched
        return None

    def _rewrite_without_history(self, query: str) -> Dict:
        """Rewrite query without history (cached)."""
        # Expand aliases first for cache key
        processed_query = self._expand_aliases(query)
        cache_key = f"{processed_query}|"
        cached = _get_cached_rewrite(cache_key)
        if cached is not None:
            return cached

        return self._rewrite_with_llm(processed_query, None)

    def _rewrite_with_history(self, query: str, history: List[Dict]) -> Dict:
        """Rewrite query with history (always uses LLM)."""
        # Expand aliases first for cache key
        processed_query = self._expand_aliases(query)
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-5:]])
        cache_key = f"{processed_query}|{history_text}"
        cached = _get_cached_rewrite(cache_key)
        if cached is not None:
            return cached

        return self._rewrite_with_llm(processed_query, history)

    def rewrite(self, query: str, history: List[Dict] = None) -> Dict:
        """Rewrite a user query.

        Returns a dict with:
          - needs_retrieval: bool
          - queries: list of rewritten queries (if needs_retrieval=True)
          - answer: str (if needs_retrieval=False, the direct answer)
          - reason: str explaining the decision
          - is_relation_query: bool indicating if this is about operator relationships
          - detected_operators: list of operator names found in the query
        """
        history = history or []

        # Expand aliases first
        query = self._expand_aliases(query)

        # Fast rule-based check FIRST - handles most common patterns without LLM
        fast_result = self._fast_rule_check(query)
        if fast_result is not None:
            return fast_result

        # Fast rule didn't match. If has pronouns AND history, need LLM
        if history and self._contains_pronouns(query):
            return self._rewrite_with_history(query, history)

        # If no history, use cached LLM rewrite
        if not history:
            return self._rewrite_without_history(query)

        # Fast rule didn't match AND has history but no pronouns: resolve references
        query = self._resolve_history_references(query, history)

        # Double-check fast_rule after reference resolution
        fast_result = self._fast_rule_check(query)
        if fast_result is not None:
            return fast_result

        # Finally, use LLM for semantic understanding
        return self._rewrite_with_history(query, history)

    def rewrite_queries_only(self, query: str, history: List[Dict] = None) -> List[str]:
        """Legacy method: only return rewritten queries (for backward compatibility)."""
        result = self.rewrite(query, history)
        if result.get("needs_retrieval"):
            return result.get("queries", [query])
        return [query]
