import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Optional
from backend.api.deepseek import DeepSeekClient

ANSWER_PROMPT_TEMPLATE = """你是一个明日方舟游戏知识问答助手。请根据以下参考资料回答用户问题。

## 对话历史
{history}

## 用户问题
{question}

## 【参考文档】（来源：本地检索，高相关性）
{documents}

## 回答要求
1. 基于参考文档内容回答，不要编造信息
2. 如果参考文档与网络搜索补充内容冲突，以参考文档为准
3. 引用相关文档时使用 [1] [2] 等标记
4. 回答应该准确、完整、简洁
5. 直接回答，不要进行深度思考或长篇推理分析

## 【网络搜索补充】（来源：网络搜索，仅作参考）
{web_results}

## 回答
"""

class AnswerGenerator:
    def __init__(self, api_key: str = None):
        # Use official DeepSeek API for answer generation (faster)
        self.client = DeepSeekClient(api_key)
        self.llm_model = "deepseek-chat"
        self.api_key = api_key

    def _build_prompt(
        self,
        question: str,
        documents: List[Dict],
        web_results: List[Dict] = None,
        graph_results: Dict = None,
        history: List[Dict] = None,
        max_documents: int = 10
    ) -> str:
        """Build the prompt for answer generation.

        Args:
            question: User question
            documents: List of retrieved documents
            web_results: Optional web search results
            graph_results: Optional GraphRAG results
            history: Optional conversation history
            max_documents: Maximum number of documents to include

        Returns:
            Formatted prompt string
        """
        # Limit documents to prevent context overflow
        documents = documents[:max_documents] if documents else []

        # Build documents section (local retrieval - high priority)
        docs_text = ""
        for i, doc in enumerate(documents, 1):  # Use all documents
            content = doc.get('content', '')  # No truncation - 8k context
            source = doc.get('metadata', {}).get('source_file', doc.get('chunk_id', f'Doc {i}'))
            score = doc.get('relevance_score', 0.0)
            score_text = f" (相关度: {score:.2f})" if score > 0 else ""
            docs_text += f"[{i}] {source}{score_text}:\n{content}\n\n"

        # Build web results section (web search supplement - lower priority)
        web_text = "无"
        if web_results:
            web_lines = []
            for i, r in enumerate(web_results, 1):
                title = r.get('title', 'Result')
                snippet = r.get('snippet', '')  # No truncation - 8k context
                score = r.get('relevance_score', 0.0)
                score_text = f" (相关度: {score:.2f})" if score > 0 else " (网络结果)"
                web_lines.append(f"[{i}] {title}{score_text}:\n{snippet}")
            web_text = "\n".join(web_lines)

        # Build graph results section
        graph_text = ""
        if graph_results and graph_results.get('is_relation_query') and graph_results.get('results'):
            operators = graph_results.get('detected_operators', [])
            results = graph_results['results']

            direct_relations = []
            individual_relations = {}

            for r in results:
                op1, op2 = r.get('operator1', ''), r.get('operator2', '')
                if op1 in operators and op2 in operators:
                    direct_relations.append(r)
                else:
                    if op1 not in individual_relations:
                        individual_relations[op1] = []
                    individual_relations[op1].append(r)

            graph_lines = []
            if direct_relations:
                graph_lines.append("【直接关系】")
                for r in direct_relations:
                    graph_lines.append(
                        f"- {r['operator1']} 与 {r['operator2']} 是{r['relation']}：{r['description']}"
                    )

            if individual_relations:
                graph_lines.append("\n【各自关系】")
                for op, rels in individual_relations.items():
                    graph_lines.append(f"\n{op} 的关系：")
                    for r in rels:  # No limit - include all relations
                        graph_lines.append(f"  - {r['operator2']}：{r['relation']}")

            graph_text = "\n## 知识图谱关系\n" + "\n".join(graph_lines) + "\n"

        # Build history text
        history_text = "无"
        if history:
            recent = history[-5:]
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

        # Build final prompt
        prompt = ANSWER_PROMPT_TEMPLATE.format(
            history=history_text,
            question=question,
            documents=docs_text,
            web_results=web_text
        )

        prompt += graph_text
        return prompt

    def generate(
        self,
        question: str,
        documents: List[Dict],
        crag_level: str = 'HIGH',
        web_results: List[Dict] = None,
        graph_results: Dict = None,
        history: List[Dict] = None,
        max_documents: int = 10
    ) -> str:
        """Generate an answer using the LLM.

        Args:
            question: User question
            documents: List of retrieved documents with content
            crag_level: CRAG level (HIGH/LOW)
            web_results: Optional web search results
            graph_results: Optional GraphRAG results
            history: Optional conversation history for resolving pronouns
            max_documents: Maximum number of documents to include

        Returns:
            Generated answer string
        """
        prompt = self._build_prompt(question, documents, web_results, graph_results, history, max_documents)

        try:
            response = self.client.chat([
                {"role": "system", "content": "你是一个明日方舟游戏知识问答助手。请基于提供的文档回答问题，保持准确和简洁。"},
                {"role": "user", "content": prompt}
            ], model=self.llm_model, extra_body={"thinking": False})
            return response.strip()
        except Exception as e:
            return f"生成回答时出错：{str(e)}"

