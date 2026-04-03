import sys
import warnings
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from backend.api.siliconflow import SiliconFlowClient
from backend.rag.query_rewriter import QueryRewriter
from backend.rag.multi_channel_recall import multi_channel_recall
from backend.rag.reranker import Reranker
from backend.rag.crag import CRAGJudge
from backend.rag.graphrag.query import GraphRAGQuery
from backend.rag.parent_document import ParentDocumentRetriever
from backend.rag.answer_generator import AnswerGenerator
from backend.storage.chroma_client import ChromaClientWrapper
from backend.data.bm25_index import BM25Indexer

@dataclass
class RAGAnswer:
    answer: str
    crag_level: str
    avg_score: float
    num_docs_used: int
    used_web_search: bool
    graph_results: Optional[Dict]
    retrieved_documents: Optional[List[Dict]] = None
    pipeline_steps: List[Dict] = field(default_factory=list)
    total_time_ms: float = 0.0

# Singleton instances for expensive components
_instance: Optional['RAGOrchestrator'] = None

def get_orchestrator(api_key: str = None, chroma_path: str = None) -> 'RAGOrchestrator':
    """Get or create singleton RAGOrchestrator instance."""
    global _instance
    if _instance is None:
        _instance = RAGOrchestrator(api_key, chroma_path)
    return _instance

class RAGOrchestrator:
    def __init__(self, api_key: str = None, chroma_path: str = None):
        self.client = SiliconFlowClient(api_key)
        self.query_rewriter = QueryRewriter(api_key)
        self.reranker = Reranker(api_key)
        self.crag_judge = CRAGJudge()
        self.graphrag_query = GraphRAGQuery(api_key)
        self.parent_retriever = ParentDocumentRetriever()
        self.answer_generator = AnswerGenerator(api_key)

        # Storage
        self.chroma_path = chroma_path or str(Path(__file__).parent.parent.parent / 'chroma_db')
        self.chroma = ChromaClientWrapper(persist_dir=self.chroma_path, embedding_client=self.client)

        # BM25 indexes (lazy load)
        self._bm25_indexes = {}
        self._bm25_loaded = False

    def _load_bm25_indexes(self):
        """Lazy load BM25 indexes with warnings for failures."""
        if self._bm25_loaded:
            return
        self._bm25_loaded = True

        for name in ['operators', 'stories', 'knowledge']:
            try:
                path = str(Path(__file__).parent.parent.parent / 'chunks') + f'/{name}_bm25.pkl'
                self._bm25_indexes[name] = BM25Indexer.load(path)
            except FileNotFoundError:
                warnings.warn(f"BM25 index not found for '{name}' collection. Search may be incomplete.")
            except Exception as e:
                warnings.warn(f"Failed to load BM25 index for '{name}' collection: {e}")

    def query(self, question: str, conversation_history: List[Dict] = None,
              use_parent_doc: bool = True,
              use_graphrag: bool = True,
              use_crag: bool = True,
              top_k_operators: int = 10,
              top_k_stories: int = 10,
              top_k_knowledge: int = 10,
              rerank_top_k: int = 5) -> RAGAnswer:
        """Execute the full RAG pipeline.

        Args:
            question: User question
            conversation_history: Optional list of previous {role, content} dicts
            use_parent_doc: Whether to use parent document expansion
            use_graphrag: Whether to use knowledge graph query
            use_crag: Whether to use CRAG judge
            top_k_operators: Top k for operators recall
            top_k_stories: Top k for stories recall
            top_k_knowledge: Top k for knowledge recall
            rerank_top_k: Top k for reranking

        Returns:
            RAGAnswer with answer, metadata
        """
        total_start = time.time()
        pipeline_steps = []
        history = conversation_history or []

        def add_step(name: str, name_cn: str, time_ms: int, description: str,
                    input_data=None, output_data=None):
            pipeline_steps.append({
                'step': len(pipeline_steps) + 1,
                'name': name,
                'name_cn': name_cn,
                'time_ms': time_ms,
                'description': description,
                'input_data': input_data,
                'output_data': output_data
            })

        # Step 1: Query rewriting (may return multiple sub-queries)
        step_start = time.time()
        input_data_step1 = {'question': question, 'history': history}
        sub_queries = self.query_rewriter.rewrite(question, history)
        step_time = round((time.time() - step_start) * 1000)
        add_step('Query Rewrite', '查询改写', step_time,
                 f'改写为 {len(sub_queries)} 个查询' if len(sub_queries) > 1 else '单查询',
                 input_data=input_data_step1,
                 output_data={'sub_queries': sub_queries})

        # Step 2: Multi-channel recall
        step_start = time.time()
        self._load_bm25_indexes()
        total_recall = top_k_operators + top_k_stories + top_k_knowledge
        recall_input = {'query': sub_queries[0] if len(sub_queries) == 1 else sub_queries,
                       'top_k_per_channel': max(top_k_operators, top_k_stories, top_k_knowledge),
                       'final_top_k': total_recall}

        if len(sub_queries) == 1:
            recall_results = multi_channel_recall(
                query=sub_queries[0],
                chroma_client=self.chroma,
                bm25_indexes=self._bm25_indexes,
                top_k_per_channel=max(top_k_operators, top_k_stories, top_k_knowledge),
                final_top_k=total_recall
            )
        else:
            all_recall = []
            for sq in sub_queries:
                results = multi_channel_recall(
                    query=sq,
                    chroma_client=self.chroma,
                    bm25_indexes=self._bm25_indexes,
                    top_k_per_channel=max(top_k_operators, top_k_stories, top_k_knowledge),
                    final_top_k=total_recall
                )
                all_recall.extend(results)

            seen = set()
            recall_results = []
            for r in all_recall:
                cid = r.get('chunk_id', '')
                if cid not in seen:
                    seen.add(cid)
                    recall_results.append(r)

        recall_output = [{'chunk_id': r.get('chunk_id', ''), 'content': r.get('content', ''),
                        'score': r.get('score', 0), 'source': r.get('source', '')}
                       for r in recall_results]
        step_time = round((time.time() - step_start) * 1000)
        add_step('Multi-Channel Recall', '多通道召回', step_time, f'召回 {len(recall_results)} 个文档',
                 input_data=recall_input,
                 output_data={'total_recalled': len(recall_results), 'top_results': recall_output})

        # Step 3: Cross-encoder rerank
        step_start = time.time()
        doc_texts = [r.get('content', '') for r in recall_results]
        doc_metadatas = [{'source_file': r.get('metadata', {}).get('source_file', ''), 'chunk_id': r.get('chunk_id', '')} for r in recall_results]

        # Each sub-query gets rerank_top_k results, then combine with deduplication
        all_reranked = []
        seen_chunk_ids = set()
        for sq in sub_queries:
            reranked = self.reranker.rerank(sq, doc_texts, top_k=rerank_top_k)
            for r in reranked:
                idx = r['index']
                chunk_id = doc_metadatas[idx].get('chunk_id', '')
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_reranked.append({
                        'content': doc_texts[idx] if idx < len(doc_texts) else '',
                        'relevance_score': r['relevance_score'],
                        'chunk_id': chunk_id,
                        'metadata': {'source_file': doc_metadatas[idx].get('source_file', '')}
                    })

        reranked_results = all_reranked

        rerank_output = [{'chunk_id': r.get('chunk_id', ''), 'relevance_score': r.get('relevance_score', 0)}
                        for r in reranked_results]
        step_time = round((time.time() - step_start) * 1000)
        add_step('Cross-Encoder Rerank', '交叉编码重排', step_time, f'重排后保留 {len(reranked_results)} 个文档',
                 input_data={'num_queries': len(sub_queries), 'num_docs': len(doc_texts), 'rerank_top_k': rerank_top_k, 'queries': sub_queries},
                 output_data={'reranked': rerank_output})

        # Step 4: CRAG judge (optional)
        crag_strategy = None
        if use_crag:
            step_start = time.time()
            crag_strategy = self.crag_judge.judge(reranked_results)
            step_time = round((time.time() - step_start) * 1000)
            add_step('CRAG Judge', 'CRAG 判断', step_time,
                     f'等级: {crag_strategy.level}, 分数: {crag_strategy.avg_score:.3f}',
                     input_data={'num_docs': len(reranked_results), 'use_crag': True},
                     output_data={'level': crag_strategy.level, 'avg_score': crag_strategy.avg_score,
                                 'should_search_web': crag_strategy.should_search_web,
                                 'num_low_score_docs': crag_strategy.num_low_score_docs,
                                 'web_search_count': crag_strategy.web_search_count})
        else:
            from dataclasses import dataclass
            # Calculate actual average score from reranked results when CRAG is disabled
            avg_score = sum(r.get('relevance_score', 0) for r in reranked_results) / len(reranked_results) if reranked_results else 0.0
            @dataclass
            class FakeStrategy:
                level: str = 'HIGH'
                should_search_web: bool = False
                avg_score: float = 0.0
                num_low_score_docs: int = 0
                web_search_count: int = 0
            crag_strategy = FakeStrategy()
            crag_strategy.avg_score = avg_score

        # Step 5: GraphRAG for relationship questions (optional)
        graph_results = None
        if use_graphrag:
            step_start = time.time()
            graph_results = self.graphrag_query.query(question)
            step_time = round((time.time() - step_start) * 1000)
            if graph_results and graph_results.get('is_relation_query'):
                graph_desc = f'检测到关系查询，找到 {len(graph_results.get("results", []))} 条关系'
            else:
                graph_desc = '非关系查询'
            add_step('GraphRAG Query', '知识图谱查询', step_time, graph_desc,
                     input_data={'question': question, 'use_graphrag': True},
                     output_data={'is_relation_query': graph_results.get('is_relation_query') if graph_results else False,
                                 'num_results': len(graph_results.get('results', [])) if graph_results else 0,
                                 'results': graph_results.get('results', []) if graph_results else []})

        # Step 6: Parent document retrieval (optional)
        if use_parent_doc:
            step_start = time.time()
            for r in reranked_results:
                chunk_id = r.get('chunk_id', '')
                if chunk_id.startswith('operators_'):
                    parent = self.parent_retriever.get_parent_content(r, 'operators')
                    r['content'] = parent
                elif chunk_id.startswith('stories_'):
                    parent = self.parent_retriever.get_parent_content(r, 'stories')
                    r['content'] = parent
            step_time = round((time.time() - step_start) * 1000)
            add_step('Parent Document', 'Parent文档扩展', step_time, '扩展文档内容',
                     input_data={'num_docs': len(reranked_results), 'use_parent_doc': True},
                     output_data={'expanded': True, 'num_docs': len(reranked_results)})

        # Step 7: Web search supplement if needed (new CRAG logic)
        step_start = time.time()
        web_results = None
        web_search_info = '跳过'
        if crag_strategy and crag_strategy.should_search_web:
            try:
                N = crag_strategy.num_low_score_docs
                search_count = crag_strategy.web_search_count

                if N > 0 and search_count > 0:
                    # Search N*2 web results
                    web_raw = self.client.search(main_query)

                    if web_raw:
                        # Extract text content from web results for reranking
                        web_texts = [r.get('snippet', '') for r in web_raw]  # No truncation - 8k context

                        # Rerank web results
                        if web_texts:
                            web_reranked = self.reranker.rerank(main_query, web_texts, top_k=min(search_count, len(web_texts)))

                            # Take top N web results
                            web_results = []
                            for r in web_reranked[:N]:
                                idx = r['index']
                                if idx < len(web_raw):
                                    web_results.append({
                                        'title': web_raw[idx].get('title', ''),
                                        'url': web_raw[idx].get('url', ''),
                                        'snippet': web_raw[idx].get('snippet', ''),
                                        'relevance_score': r['relevance_score'],
                                        'source': 'web_search'
                                    })

                            web_search_info = f'补充 {N} 篇网络结果'
                        else:
                            web_search_info = '无网络结果'
                    else:
                        web_search_info = '搜索失败'
                else:
                    web_search_info = '无需补充'

            except Exception as e:
                web_search_info = f'搜索异常: {str(e)[:20]}'
        step_time = round((time.time() - step_start) * 1000)
        add_step('Web Search', '网络搜索', step_time, web_search_info,
                 input_data={'should_search_web': crag_strategy.should_search_web if crag_strategy else False},
                 output_data={'web_results_count': len(web_results) if web_results else 0,
                             'search_info': web_search_info})

        # Step 8: Generate answer
        step_start = time.time()
        answer = self.answer_generator.generate(
            question=question,
            documents=reranked_results,
            crag_level=crag_strategy.level if crag_strategy else 'HIGH',
            web_results=web_results,
            graph_results=graph_results if (graph_results and graph_results.get('is_relation_query')) else None
        )
        step_time = round((time.time() - step_start) * 1000)
        add_step('Answer Generation', '答案生成', step_time, '生成最终回答',
                 input_data={'question': question, 'num_docs': len(reranked_results),
                            'crag_level': crag_strategy.level if crag_strategy else 'HIGH',
                            'has_web_results': bool(web_results),
                            'has_graph_results': bool(graph_results and graph_results.get('is_relation_query'))},
                 output_data={'answer_length': len(answer), 'answer_full': answer})

        total_time = round((time.time() - total_start) * 1000)

        return RAGAnswer(
            answer=answer,
            crag_level=crag_strategy.level,
            avg_score=crag_strategy.avg_score,
            num_docs_used=len(reranked_results),
            used_web_search=crag_strategy.should_search_web,
            graph_results=graph_results if (graph_results and graph_results.get('is_relation_query')) else None,
            retrieved_documents=reranked_results,
            pipeline_steps=pipeline_steps,
            total_time_ms=total_time
        )

    def run_debug_step(self, step: int, question: str, conversation_history: List[Dict] = None,
                       previous_results: Dict[int, Any] = None,
                       use_parent_doc: bool = True,
                       use_graphrag: bool = True,
                       use_crag: bool = True,
                       top_k_operators: int = 10,
                       top_k_stories: int = 10,
                       top_k_knowledge: int = 10,
                       rerank_top_k: int = 5) -> Dict[str, Any]:
        """Run a specific RAG step and return its output.

        Args:
            step: Step number (1-8) to execute
            question: User question
            conversation_history: Optional conversation history
            previous_results: Dict of previous step outputs {step_num: output}
            use_parent_doc: Whether to use parent document expansion
            use_graphrag: Whether to use knowledge graph query
            use_crag: Whether to use CRAG judge
            top_k_operators: Top k for operators recall
            top_k_stories: Top k for stories recall
            top_k_knowledge: Top k for knowledge recall
            rerank_top_k: Top k for reranking

        Returns:
            Dict with step info and output
        """
        import json
        history = conversation_history or []

        step_info = {
            1: ('Query Rewrite', '查询改写'),
            2: ('Multi-Channel Recall', '多通道召回'),
            3: ('Cross-Encoder Rerank', '交叉编码重排'),
            4: ('CRAG Judge', 'CRAG 判断'),
            5: ('GraphRAG Query', '知识图谱查询'),
            6: ('Parent Document', 'Parent文档扩展'),
            7: ('Web Search', '网络搜索'),
            8: ('Answer Generation', '答案生成'),
        }

        name, name_cn = step_info.get(step, ('Unknown', '未知'))

        # Build context from previous results
        sub_queries = None
        recall_results = None
        reranked_results = None
        crag_strategy = None
        graph_results = None
        web_results = None

        # Reconstruct state from previous results
        if previous_results:
            for prev_step, prev_output in previous_results.items():
                if prev_step == 1:
                    sub_queries = prev_output if isinstance(prev_output, list) else [prev_output]
                elif prev_step == 2:
                    # Ensure it's a list, not a string or other type
                    recall_results = prev_output if isinstance(prev_output, list) else None
                elif prev_step == 3:
                    # Ensure it's a list, not a string or other type
                    reranked_results = prev_output if isinstance(prev_output, list) else None
                elif prev_step == 4:
                    # CRAG result
                    if isinstance(prev_output, dict):
                        from dataclasses import dataclass
                        @dataclass
                        class FakeStrategy:
                            level: str = 'HIGH'
                            should_search_web: bool = False
                            avg_score: float = 0.0
                            num_low_score_docs: int = 0
                            web_search_count: int = 0
                        crag_strategy = FakeStrategy()
                        if 'level' in prev_output:
                            crag_strategy.level = prev_output['level']
                        if 'should_search_web' in prev_output:
                            crag_strategy.should_search_web = prev_output['should_search_web']
                        if 'avg_score' in prev_output:
                            crag_strategy.avg_score = prev_output['avg_score']
                        if 'num_low_score_docs' in prev_output:
                            crag_strategy.num_low_score_docs = prev_output['num_low_score_docs']
                        if 'web_search_count' in prev_output:
                            crag_strategy.web_search_count = prev_output['web_search_count']
                    else:
                        crag_strategy = prev_output if not isinstance(prev_output, str) else None
                elif prev_step == 5:
                    # Ensure it's a dict, not a string
                    graph_results = prev_output if isinstance(prev_output, dict) else None
                elif prev_step == 6:
                    # Parent doc returns {'expanded': True, 'num_docs': N, 'documents': [...]}
                    if isinstance(prev_output, dict) and 'documents' in prev_output:
                        reranked_results = prev_output['documents']
                elif prev_step == 7:
                    # Check if output is an error (web search failed) or invalid type
                    if isinstance(prev_output, dict) and 'error' in prev_output:
                        web_results = None
                    else:
                        web_results = prev_output if isinstance(prev_output, list) else None

        result = {'step': step, 'name': name, 'name_cn': name_cn, 'can_continue': step < 8}

        try:
            step_start = time.time()

            if step == 1:
                # Query rewriting
                output = self.query_rewriter.rewrite(question, history)
                result['input_data'] = {'question': question, 'history': history}
                result['output_data'] = output

            elif step == 2:
                # Multi-channel recall
                self._load_bm25_indexes()
                query = sub_queries[0] if sub_queries else question
                output = multi_channel_recall(
                    query=query,
                    chroma_client=self.chroma,
                    bm25_indexes=self._bm25_indexes,
                    top_k_per_channel=max(top_k_operators, top_k_stories, top_k_knowledge),
                    final_top_k=top_k_operators + top_k_stories + top_k_knowledge
                )
                result['input_data'] = {'query': query}
                result['output_data'] = [{'chunk_id': r.get('chunk_id', ''), 'content': r.get('content', '')} for r in output]

            elif step == 3:
                # Cross-encoder rerank
                if not recall_results:
                    raise ValueError('Step 2 (recall) must be executed first')
                doc_texts = [r.get('content', '') for r in recall_results]
                reranked = self.reranker.rerank(question, doc_texts, top_k=rerank_top_k)
                output = []
                for r in reranked:
                    idx = r['index']
                    output.append({
                        'chunk_id': recall_results[idx].get('chunk_id', ''),
                        'content': recall_results[idx].get('content', ''),
                        'relevance_score': r['relevance_score']
                    })
                result['input_data'] = {'query': question, 'num_docs': len(recall_results)}
                result['output_data'] = output

            elif step == 4:
                # CRAG judge
                if not reranked_results:
                    raise ValueError('Step 3 (rerank) must be executed first')
                if not use_crag:
                    from dataclasses import dataclass
                    # Calculate actual average score from reranked results when CRAG is disabled
                    avg_score = sum(r.get('relevance_score', 0) for r in reranked_results) / len(reranked_results) if reranked_results else 0.0
                    @dataclass
                    class FakeStrategy:
                        level: str = 'HIGH'
                        should_search_web: bool = False
                        avg_score: float = 0.0
                        num_low_score_docs: int = 0
                        web_search_count: int = 0
                    output = FakeStrategy()
                    output.avg_score = avg_score
                else:
                    output = self.crag_judge.judge(reranked_results)
                result['input_data'] = {'num_docs': len(reranked_results)}
                result['output_data'] = {
                    'level': output.level,
                    'should_search_web': output.should_search_web,
                    'avg_score': output.avg_score,
                    'num_low_score_docs': output.num_low_score_docs,
                    'web_search_count': output.web_search_count
                }

            elif step == 5:
                # GraphRAG query
                if not use_graphrag:
                    result['input_data'] = {'question': question}
                    result['output_data'] = {'disabled': True, 'message': '知识图谱已禁用'}
                else:
                    output = self.graphrag_query.query(question)
                    result['input_data'] = {'question': question}
                    result['output_data'] = {
                        'is_relation_query': output.get('is_relation_query', False) if output else False,
                        'num_results': len(output.get('results', [])) if output else 0
                    }

            elif step == 6:
                # Parent document
                if not use_parent_doc:
                    result['input_data'] = {'num_docs': len(reranked_results) if reranked_results else 0}
                    result['output_data'] = {'disabled': True, 'message': 'Parent文档已禁用'}
                else:
                    if not reranked_results:
                        raise ValueError('Step 3 (rerank) must be executed first')
                    expanded_docs = []
                    for r in reranked_results:
                        chunk_id = r.get('chunk_id', '')
                        if chunk_id.startswith('operators_'):
                            parent = self.parent_retriever.get_parent_content(r, 'operators')
                            r['content'] = parent
                        elif chunk_id.startswith('stories_'):
                            parent = self.parent_retriever.get_parent_content(r, 'stories')
                            r['content'] = parent
                        expanded_docs.append(r)
                    result['input_data'] = {'num_docs': len(reranked_results)}
                    result['output_data'] = {'expanded': True, 'num_docs': len(expanded_docs), 'documents': expanded_docs}

            elif step == 7:
                # Web search
                if not crag_strategy or not crag_strategy.should_search_web:
                    result['input_data'] = {'query': question}
                    result['output_data'] = {'skipped': True, 'reason': 'CRAG未触发网络搜索'}
                    web_results = None
                else:
                    try:
                        output = self.client.search(question)
                        result['input_data'] = {'query': question}
                        result['output_data'] = {'num_results': len(output) if output else 0}
                        web_results = output
                    except Exception as e:
                        result['input_data'] = {'query': question}
                        result['output_data'] = {'error': str(e), 'skipped': True}
                        web_results = None

            elif step == 8:
                # Answer generation
                answer = self.answer_generator.generate(
                    question=question,
                    documents=reranked_results or [],
                    crag_level=crag_strategy.level if crag_strategy else 'HIGH',
                    web_results=web_results,
                    graph_results=graph_results if (graph_results and graph_results.get('is_relation_query')) else None
                )
                result['input_data'] = {
                    'question': question,
                    'num_docs': len(reranked_results) if reranked_results else 0,
                    'has_web_results': bool(web_results),
                    'has_graph_results': bool(graph_results and graph_results.get('is_relation_query'))
                }
                result['output_data'] = {'answer': answer}

            step_time = round((time.time() - step_start) * 1000)
            result['time_ms'] = step_time
            result['error'] = None

        except Exception as e:
            result['time_ms'] = round((time.time() - step_start) * 1000) if 'step_start' in locals() else 0
            result['output_data'] = {'error': str(e)}
            result['error'] = str(e)

        return result

    def query_stream(self, question: str, conversation_history: List[Dict] = None,
                     use_parent_doc: bool = True,
                     use_graphrag: bool = True,
                     use_crag: bool = True,
                     top_k_operators: int = 10,
                     top_k_stories: int = 10,
                     top_k_knowledge: int = 10,
                     rerank_top_k: int = 5):
        """Execute the full RAG pipeline with streaming.

        Yields SSE events for each step and then streams the answer.

        Args:
            question: User question
            conversation_history: Optional list of previous {role, content} dicts
            use_parent_doc: Whether to use parent document expansion
            use_graphrag: Whether to use knowledge graph query
            use_crag: Whether to use CRAG judge
            top_k_operators: Top k for operators recall
            top_k_stories: Top k for stories recall
            top_k_knowledge: Top k for knowledge recall
            rerank_top_k: Top k for reranking

        Yields:
            SSE-formatted event strings
        """
        import json
        history = conversation_history or []

        def sse_event(event_type: str, data: dict):
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        total_start = time.time()

        # Step 1: Query rewriting
        step_start = time.time()
        sub_queries = self.query_rewriter.rewrite(question, history)
        step_time = round((time.time() - step_start) * 1000)
        yield sse_event('step', {
            'step': 1,
            'name': 'Query Rewrite',
            'name_cn': '查询改写',
            'time_ms': step_time,
            'description': f'改写为 {len(sub_queries)} 个查询' if len(sub_queries) > 1 else '单查询',
            'input_data': {'question': question, 'history': history},
            'output_data': {'sub_queries': sub_queries}
        })

        # Step 2: Multi-channel recall
        step_start = time.time()
        self._load_bm25_indexes()
        total_recall = top_k_operators + top_k_stories + top_k_knowledge

        if len(sub_queries) == 1:
            recall_results = multi_channel_recall(
                query=sub_queries[0],
                chroma_client=self.chroma,
                bm25_indexes=self._bm25_indexes,
                top_k_per_channel=max(top_k_operators, top_k_stories, top_k_knowledge),
                final_top_k=total_recall
            )
        else:
            all_recall = []
            for sq in sub_queries:
                results = multi_channel_recall(
                    query=sq,
                    chroma_client=self.chroma,
                    bm25_indexes=self._bm25_indexes,
                    top_k_per_channel=max(top_k_operators, top_k_stories, top_k_knowledge),
                    final_top_k=total_recall
                )
                all_recall.extend(results)

            seen = set()
            recall_results = []
            for r in all_recall:
                cid = r.get('chunk_id', '')
                if cid not in seen:
                    seen.add(cid)
                    recall_results.append(r)

        step_time = round((time.time() - step_start) * 1000)
        recall_output = [{'chunk_id': r.get('chunk_id', ''), 'content': r.get('content', ''),
                        'score': r.get('score', 0), 'source': r.get('source', '')}
                       for r in recall_results]
        yield sse_event('step', {
            'step': 2,
            'name': 'Multi-Channel Recall',
            'name_cn': '多通道召回',
            'time_ms': step_time,
            'description': f'召回 {len(recall_results)} 个文档',
            'input_data': {'query': sub_queries[0] if len(sub_queries) == 1 else sub_queries,
                          'top_k_per_channel': max(top_k_operators, top_k_stories, top_k_knowledge),
                          'final_top_k': total_recall},
            'output_data': {'total_recalled': len(recall_results), 'top_results': recall_output}
        })

        # Step 3: Cross-encoder rerank
        step_start = time.time()
        doc_texts = [r.get('content', '') for r in recall_results]
        doc_metadatas = [{'source_file': r.get('metadata', {}).get('source_file', ''), 'chunk_id': r.get('chunk_id', '')} for r in recall_results]

        # Each sub-query gets rerank_top_k results, then combine with deduplication
        all_reranked = []
        seen_chunk_ids = set()
        for sq in sub_queries:
            reranked = self.reranker.rerank(sq, doc_texts, top_k=rerank_top_k)
            for r in reranked:
                idx = r['index']
                chunk_id = doc_metadatas[idx].get('chunk_id', '')
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_reranked.append({
                        'content': doc_texts[idx] if idx < len(doc_texts) else '',
                        'relevance_score': r['relevance_score'],
                        'chunk_id': chunk_id,
                        'metadata': {'source_file': doc_metadatas[idx].get('source_file', '')}
                    })

        reranked_results = all_reranked

        step_time = round((time.time() - step_start) * 1000)
        rerank_output = [{'chunk_id': r.get('chunk_id', ''), 'relevance_score': r.get('relevance_score', 0)}
                        for r in reranked_results]
        yield sse_event('step', {
            'step': 3,
            'name': 'Cross-Encoder Rerank',
            'name_cn': '交叉编码重排',
            'time_ms': step_time,
            'description': f'重排后保留 {len(reranked_results)} 个文档',
            'input_data': {'num_queries': len(sub_queries), 'num_docs': len(doc_texts), 'rerank_top_k': rerank_top_k, 'queries': sub_queries},
            'output_data': {'reranked': rerank_output}
        })

        # Step 4: CRAG judge
        crag_strategy = None
        if use_crag:
            step_start = time.time()
            crag_strategy = self.crag_judge.judge(reranked_results)
            step_time = round((time.time() - step_start) * 1000)
            yield sse_event('step', {
                'step': 4,
                'name': 'CRAG Judge',
                'name_cn': 'CRAG 判断',
                'time_ms': step_time,
                'description': f'等级: {crag_strategy.level}, 分数: {crag_strategy.avg_score:.3f}',
                'input_data': {'num_docs': len(reranked_results), 'use_crag': True},
                'output_data': {'level': crag_strategy.level, 'avg_score': crag_strategy.avg_score,
                               'should_search_web': crag_strategy.should_search_web,
                               'num_low_score_docs': crag_strategy.num_low_score_docs,
                               'web_search_count': crag_strategy.web_search_count}
            })
        else:
            from dataclasses import dataclass
            @dataclass
            class FakeStrategy:
                level: str = 'HIGH'
                should_search_web: bool = False
                avg_score: float = 0.0
                num_low_score_docs: int = 0
                web_search_count: int = 0
            crag_strategy = FakeStrategy()

        # Step 5: GraphRAG
        graph_results = None
        if use_graphrag:
            step_start = time.time()
            graph_results = self.graphrag_query.query(question)
            step_time = round((time.time() - step_start) * 1000)
            if graph_results and graph_results.get('is_relation_query'):
                graph_desc = f'检测到关系查询，找到 {len(graph_results.get("results", []))} 条关系'
            else:
                graph_desc = '非关系查询'
            yield sse_event('step', {
                'step': 5,
                'name': 'GraphRAG Query',
                'name_cn': '知识图谱查询',
                'time_ms': step_time,
                'description': graph_desc,
                'input_data': {'question': question, 'use_graphrag': True},
                'output_data': {'is_relation_query': graph_results.get('is_relation_query') if graph_results else False,
                               'num_results': len(graph_results.get('results', [])) if graph_results else 0,
                               'results': graph_results.get('results', [])[:5] if graph_results else []}
            })

        # Step 6: Parent document
        if use_parent_doc:
            step_start = time.time()
            for r in reranked_results:
                chunk_id = r.get('chunk_id', '')
                if chunk_id.startswith('operators_'):
                    parent = self.parent_retriever.get_parent_content(r, 'operators')
                    r['content'] = parent
                elif chunk_id.startswith('stories_'):
                    parent = self.parent_retriever.get_parent_content(r, 'stories')
                    r['content'] = parent
            step_time = round((time.time() - step_start) * 1000)
            yield sse_event('step', {
                'step': 6,
                'name': 'Parent Document',
                'name_cn': 'Parent文档扩展',
                'time_ms': step_time,
                'description': '扩展文档内容',
                'input_data': {'num_docs': len(reranked_results), 'use_parent_doc': True},
                'output_data': {'expanded': True, 'num_docs': len(reranked_results)}
            })

        # Step 7: Web search
        step_start = time.time()
        web_results = None
        web_search_info = '跳过'
        if crag_strategy and crag_strategy.should_search_web:
            try:
                N = crag_strategy.num_low_score_docs
                search_count = crag_strategy.web_search_count

                if N > 0 and search_count > 0:
                    web_raw = self.client.search(main_query)

                    if web_raw:
                        web_texts = [r.get('snippet', '') for r in web_raw]

                        if web_texts:
                            web_reranked = self.reranker.rerank(main_query, web_texts, top_k=min(search_count, len(web_texts)))

                            web_results = []
                            for r in web_reranked[:N]:
                                idx = r['index']
                                if idx < len(web_raw):
                                    web_results.append({
                                        'title': web_raw[idx].get('title', ''),
                                        'url': web_raw[idx].get('url', ''),
                                        'snippet': web_raw[idx].get('snippet', ''),
                                        'relevance_score': r['relevance_score'],
                                        'source': 'web_search'
                                    })

                            web_search_info = f'补充 {N} 篇网络结果'
                        else:
                            web_search_info = '无网络结果'
                    else:
                        web_search_info = '搜索失败'
                else:
                    web_search_info = '无需补充'

            except Exception as e:
                web_search_info = f'搜索异常: {str(e)[:20]}'
        step_time = round((time.time() - step_start) * 1000)
        yield sse_event('step', {
            'step': 7,
            'name': 'Web Search',
            'name_cn': '网络搜索',
            'time_ms': step_time,
            'description': web_search_info,
            'input_data': {'should_search_web': crag_strategy.should_search_web if crag_strategy else False},
            'output_data': {'web_results_count': len(web_results) if web_results else 0, 'search_info': web_search_info}
        })

        # Step 8: Generate answer (streaming)
        step_start = time.time()
        yield sse_event('step', {
            'step': 8,
            'name': 'Answer Generation',
            'name_cn': '答案生成',
            'time_ms': 0,
            'description': '流式生成中...',
            'input_data': {'question': question, 'num_docs': len(reranked_results),
                          'crag_level': crag_strategy.level if crag_strategy else 'HIGH',
                          'has_web_results': bool(web_results),
                          'has_graph_results': bool(graph_results and graph_results.get('is_relation_query'))},
            'output_data': {'status': 'streaming'}
        })

        # Stream the answer
        full_answer = []
        for chunk in self.answer_generator.generate_stream(
            question=question,
            documents=reranked_results,
            crag_level=crag_strategy.level if crag_strategy else 'HIGH',
            web_results=web_results,
            graph_results=graph_results if (graph_results and graph_results.get('is_relation_query')) else None
        ):
            full_answer.append(chunk)
            yield sse_event('answer_chunk', {'chunk': chunk})

        final_answer = ''.join(full_answer)
        step_time = round((time.time() - step_start) * 1000)
        total_time = round((time.time() - total_start) * 1000)

        # Send final summary
        yield sse_event('done', {
            'answer': final_answer,
            'crag_level': crag_strategy.level if crag_strategy else 'HIGH',
            'avg_score': crag_strategy.avg_score if crag_strategy else 1.0,
            'num_docs_used': len(reranked_results),
            'used_web_search': crag_strategy.should_search_web if crag_strategy else False,
            'graph_results': graph_results if (graph_results and graph_results.get('is_relation_query')) else None,
            'retrieved_documents': reranked_results,
            'total_time_ms': total_time,
            'step_8_time_ms': step_time
        })