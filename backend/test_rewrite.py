"""测试 QueryRewriter 的速度和多代词处理"""
import time
import sys
sys.path.insert(0, '.')

# Test cases: (query, history, description)
test_cases = [
    ('狮蝎别名有什么', [], '无历史-无代词'),
    ('银灰技能是什么', [], '无历史-无代词-技能'),
    ('维什戴尔技能是什么', [], '无历史-无代词'),
    ('她的别名是什么', [{'role': 'user', 'content': '维什戴尔的技能是什么'}], '有历史-代词'),
    ('她们的关系是什么', [{'role': 'user', 'content': '维什戴尔的技能是什么，迷迭香的技能是什么'}], '有历史-代词-多干员'),
    ('那银灰呢', [{'role': 'user', 'content': '维什戴尔技能'}, {'role': 'assistant', 'content': '维什戴尔是六星'}], '有历史-那指代'),
    ('她的背景故事是什么', [{'role': 'user', 'content': '银灰技能'}], '有历史-代词-背景'),
    ('他和她的关系', [{'role': 'user', 'content': '银灰'}, {'role': 'assistant', 'content': '银灰是六星辅助'}], '有历史-多代词'),
]

print('测试 QueryRewriter (DeepSeek) 速度:')
print('=' * 60)

from rag.query_rewriter import QueryRewriter
rewriter = QueryRewriter()

for query, history, desc in test_cases:
    start = time.time()
    result = rewriter.rewrite(query, history)
    elapsed = time.time() - start
    print(f'{desc}: {elapsed:.2f}s')
    print(f'  Query: {query}')
    print(f'  needs_retrieval: {result.get("needs_retrieval")}')
    print(f'  queries: {result.get("queries", [])}')
    print(f'  is_relation_query: {result.get("is_relation_query")}')
    if result.get("detected_operators"):
        print(f'  detected_operators: {result.get("detected_operators")}')
    print()
