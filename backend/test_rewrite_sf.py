"""测试 SiliconFlow Qwen 的重写速度"""
import time
import sys
sys.path.insert(0, '.')

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

print('测试 SiliconFlow Qwen 速度:')
print('=' * 60)

from api.siliconflow import SiliconFlowClient

# Use SiliconFlow Qwen for chat
client = SiliconFlowClient()

def rewrite_with_qwen(query, history):
    """用 Qwen 重写查询"""
    history_text = ""
    if history:
        recent = history[-5:]
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

    prompt = f"""你是一个明日方舟RAG聊天助手，根据用户问题判断是否需要检索知识库。

## 判断标准
需要检索：询问干员属性、技能、关系、背景等具体信息
不需要检索：日常闲聊、自我介绍等

## 输出格式（JSON，不要代码块）
{{"needs_retrieval": true/false, "queries": ["改写查询"], "is_relation_query": true/false, "detected_operators": []}}

## 对话历史
{history_text if history_text else "无"}

## 用户问题
{query}

## JSON输出
"""
    try:
        response = client.chat([
            {"role": "system", "content": "你是一个明日方舟RAG助手，直接输出JSON。"},
            {"role": "user", "content": prompt}
        ], model="Qwen/Qwen2.5-7B-Instruct")

        import json
        raw = response.strip()
        if raw.startswith('```'):
            lines = raw.split('\n')
            if lines[0].strip().startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip().endswith('```'):
                lines = lines[:-1]
            raw = '\n'.join(lines)
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e), "needs_retrieval": True, "queries": [query]}

for query, history, desc in test_cases:
    start = time.time()
    result = rewrite_with_qwen(query, history)
    elapsed = time.time() - start
    print(f'{desc}: {elapsed:.2f}s')
    print(f'  Query: {query}')
    if "error" in result:
        print(f'  Error: {result["error"]}')
    else:
        print(f'  needs_retrieval: {result.get("needs_retrieval")}')
        print(f'  queries: {result.get("queries", [])}')
        print(f'  is_relation_query: {result.get("is_relation_query")}')
        if result.get("detected_operators"):
            print(f'  detected_operators: {result.get("detected_operators")}')
    print()
