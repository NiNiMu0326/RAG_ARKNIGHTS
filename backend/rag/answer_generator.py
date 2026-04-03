import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from typing import List, Dict, Optional
from backend.api.siliconflow import SiliconFlowClient

ANSWER_PROMPT_TEMPLATE = """你是一个明日方舟游戏知识问答助手。请根据以下参考资料回答用户问题。

## 用户问题
{question}

## 【参考文档】（来源：本地检索，高相关性）
{documents}

## 回答要求
1. 基于参考文档内容回答，不要编造信息
2. 如果参考文档与网络搜索补充内容冲突，以参考文档为准
3. 引用相关文档时使用 [1] [2] 等标记
4. 回答应该准确、完整、简洁

## 【网络搜索补充】（来源：网络搜索，仅作参考）
{web_results}

## 回答
"""

class AnswerGenerator:
    def __init__(self, api_key: str = None):
        self.client = SiliconFlowClient(api_key)
        self.api_key = api_key

    def generate(
        self,
        question: str,
        documents: List[Dict],
        crag_level: str = 'HIGH',
        web_results: List[Dict] = None,
        graph_results: Dict = None
    ) -> str:
        """Generate an answer using the LLM.

        Args:
            question: User question
            documents: List of retrieved documents with content
            crag_level: CRAG level (HIGH/MEDIUM/LOW)
            web_results: Optional web search results
            graph_results: Optional GraphRAG results

        Returns:
            Generated answer string
        """
        # Build documents section (local retrieval - high priority)
        docs_text = ""
        for i, doc in enumerate(documents[:5], 1):  # Max 5 docs
            content = doc.get('content', '')  # No truncation - 8k context
            source = doc.get('metadata', {}).get('source_file', doc.get('chunk_id', f'Doc {i}'))
            score = doc.get('relevance_score', 0.0)
            docs_text += f"[{i}] {source} (相关度: {score:.2f}):\n{content}\n\n"

        # Build web results section (web search supplement - lower priority)
        web_text = "无"
        if web_results:
            web_lines = []
            for i, r in enumerate(web_results, 1):
                title = r.get('title', 'Result')
                snippet = r.get('snippet', '')  # No truncation - 8k context
                score = r.get('relevance_score', 0.0)
                web_lines.append(f"[{i}] {title} (相关度: {score:.2f}):\n{snippet}")
            web_text = "\n".join(web_lines)

        # Build graph results section
        graph_text = ""
        if graph_results and graph_results.get('is_relation_query') and graph_results.get('results'):
            # Check if there's a direct relationship between the operators
            operators = graph_results.get('detected_operators', [])
            results = graph_results['results']

            # Separate direct relations (operators connected to each other) from individual relations
            direct_relations = []
            individual_relations = {}

            for r in results:
                op1, op2 = r.get('operator1', ''), r.get('operator2', '')
                # Check if this is a direct relation between two detected operators
                if op1 in operators and op2 in operators:
                    direct_relations.append(r)
                else:
                    # Collect individual relations grouped by operator
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

        # Build final prompt
        prompt = ANSWER_PROMPT_TEMPLATE.format(
            question=question,
            documents=docs_text,
            web_results=web_text
        )

        prompt += graph_text

        try:
            response = self.client.chat([
                {"role": "system", "content": "你是一个明日方舟游戏知识问答助手。请基于提供的文档回答问题，保持准确和简洁。"},
                {"role": "user", "content": prompt}
            ])
            return response.strip()
        except Exception as e:
            return f"生成回答时出错：{str(e)}"

    def generate_stream(
        self,
        question: str,
        documents: List[Dict],
        crag_level: str = 'HIGH',
        web_results: List[Dict] = None,
        graph_results: Dict = None
    ):
        """Generate an answer using the LLM with streaming.

        Args:
            question: User question
            documents: List of retrieved documents with content
            crag_level: CRAG level (HIGH/MEDIUM/LOW)
            web_results: Optional web search results
            graph_results: Optional GraphRAG results

        Yields:
            Chunks of generated answer
        """
        # Build documents section (local retrieval - high priority)
        docs_text = ""
        for i, doc in enumerate(documents[:5], 1):  # Max 5 docs
            content = doc.get('content', '')
            source = doc.get('metadata', {}).get('source_file', doc.get('chunk_id', f'Doc {i}'))
            score = doc.get('relevance_score', 0.0)
            docs_text += f"[{i}] {source} (相关度: {score:.2f}):\n{content}\n\n"

        # Build web results section (web search supplement - lower priority)
        web_text = "无"
        if web_results:
            web_lines = []
            for i, r in enumerate(web_results, 1):
                title = r.get('title', 'Result')
                snippet = r.get('snippet', '')
                score = r.get('relevance_score', 0.0)
                web_lines.append(f"[{i}] {title} (相关度: {score:.2f}):\n{snippet}")
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
                    for r in rels:
                        graph_lines.append(f"  - {r['operator2']}：{r['relation']}")

            graph_text = "\n## 知识图谱关系\n" + "\n".join(graph_lines) + "\n"

        # Build final prompt
        prompt = ANSWER_PROMPT_TEMPLATE.format(
            question=question,
            documents=docs_text,
            web_results=web_text
        )

        prompt += graph_text

        try:
            for chunk in self.client.chat_stream([
                {"role": "system", "content": "你是一个明日方舟游戏知识问答助手。请基于提供的文档回答问题，保持准确和简洁。"},
                {"role": "user", "content": prompt}
            ]):
                yield chunk
        except Exception as e:
            yield f"生成回答时出错：{str(e)}"