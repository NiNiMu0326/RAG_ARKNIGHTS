"""全面测试 QueryRewriter 重写质量和速度"""
import time
import json
import sys
sys.path.insert(0, '.')

# 更多测试用例，覆盖各种场景
test_cases = [
    # === 无历史无代词 ===
    ('狮蝎别名有什么', [], '狮蝎 别名', '无历史-别名'),
    ('银灰的技能是什么', [], '银灰 技能', '无历史-技能'),
    ('维什戴尔的背景故事是什么', [], '维什戴尔 背景', '无历史-背景故事'),
    ('迷迭香的关系是什么', [], '迷迭香 关系', '无历史-关系'),
    ('陈是谁', [], '陈 身份', '无历史-身份'),
    ('德克萨斯皮肤有哪些', [], '德克萨斯 皮肤', '无历史-皮肤'),
    ('明日方舟公招攻略', [], '明日方舟 公招', '无历史-攻略'),
    ('银灰怎么获得', [], '银灰 获取', '无历史-获取方式'),
    ('史尔特尔天赋是什么', [], '史尔特尔 天赋', '无历史-天赋'),
    ('能天使皮肤', [], '能天使 皮肤', '无历史-皮肤简称'),

    # === 有历史无代词 ===
    ('维什戴尔的技能是什么', [], '维什戴尔 技能', '无历史-技能2'),
    ('她的别名是什么', [{'role': 'user', 'content': '维什戴尔的技能是什么'}], '维什戴尔 别名', '有历史-代词-别名'),
    ('那银灰呢', [{'role': 'user', 'content': '维什戴尔技能'}, {'role': 'assistant', 'content': '维什戴尔是六星'}], '银灰 技能', '有历史-那指代'),
    ('她的背景故事呢', [{'role': 'user', 'content': '银灰技能'}], '银灰 背景', '有历史-代词-背景'),
    ('他的天赋是什么', [{'role': 'user', 'content': '史尔特尔技能'}], '史尔特尔 天赋', '有历史-代词-天赋'),
    ('那她的关系呢', [{'role': 'user', 'content': '银灰'}, {'role': 'assistant', 'content': '银灰是六星辅助'}], '银灰 关系', '有历史-那指代-关系'),

    # === 有历史有代词-多干员 ===
    ('她们的关系是什么', [{'role': 'user', 'content': '维什戴尔的技能是什么，迷迭香的技能是什么'}], '维什戴尔 迷迭香 关系', '有历史-代词-多干员关系'),
    ('他和她的关系', [{'role': 'user', 'content': '银灰技能'}, {'role': 'assistant', 'content': '银灰是六星辅助'}], '银灰 她 关系', '有历史-代词-多干员关系2'),
    ('她们有什么关系', [{'role': 'user', 'content': '能天使'}, {'role': 'assistant', 'content': '能天使是三星'}], '能天使 她 关系', '有历史-代词-多干员关系3'),

    # === 无历史有代词 ===
    ('她的别名是什么', [], '她 别名', '无历史-代词-别名'),
    ('他技能是什么', [], '他 技能', '无历史-代词-技能'),
    ('它的背景故事是什么', [], '它 背景', '无历史-代词-背景'),

    # === 闲聊不检索 ===
    ('你好', [], None, '闲聊-问候'),
    ('今天天气不错', [], None, '闲聊-天气'),
    ('你是谁', [], None, '闲聊-身份'),
    ('随便聊聊', [], None, '闲聊-随便'),
    ('你觉得银灰怎么样', [], None, '闲聊-看法'),

    # === 复杂查询 ===
    ('银灰和初雪什么关系', [], '银灰 初雪 关系', '无历史-双干员关系'),
    ('维什戴尔和史尔特尔谁更强', [], '维什戴尔 史尔特尔', '无历史-对比'),
    ('赫默和塞雷娅是什么关系', [], '赫默 塞雷娅 关系', '无历史-双干员关系2'),
]

def test_siliconflow_qwen():
    """测试 SiliconFlow Qwen"""
    from api.siliconflow import SiliconFlowClient
    client = SiliconFlowClient()

    results = {'total': 0, 'correct': 0, 'errors': 0, 'by_category': {}}

    def rewrite(query, history):
        history_text = ""
        if history:
            recent = history[-5:]
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

        # 改进的 prompt，期望输出简短关键词格式
        prompt = f"""你是一个明日方舟RAG查询改写助手。请根据对话历史改写用户问题。

## 任务
1. 判断是否需要检索知识库（需要：干员信息/剧情/攻略等；不需要：闲聊/问候/自我回答等）
2. 如果需要检索，将问题改写为简短的关键词组合，格式如：
   - "银灰技能" → "银灰 技能"
   - "维什戴尔和史尔特尔关系" → "维什戴尔 史尔特尔 关系"
   - "她的别名是什么" → "她 别名"（保留代词让LLM理解）
3. 如果不需要检索，返回 needs_retrieval=false

## 判断标准
需要检索：干员属性、技能、天赋、关系、背景、获取方式、攻略等具体信息
不需要检索：问候、自我介绍、天气闲聊、询问看法等

## 输出格式（纯JSON，不要代码块）
{{"needs_retrieval": true或false, "queries": ["关键词1 关键词2"], "is_relation_query": true或false, "detected_operators": ["干员1", "干员2"]}}

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

    print("=" * 80)
    print("SiliconFlow Qwen 测试结果")
    print("=" * 80)

    current_category = None
    for query, history, expected_query, desc in test_cases:
        results['total'] += 1

        # 跟踪类别变化
        cat = desc.split('-')[0]
        if cat != current_category:
            current_category = cat
            print(f"\n{'='*40}")
            print(f"  {cat}")
            print(f"{'='*40}")

        start = time.time()
        result = rewrite(query, history)
        elapsed = time.time() - start

        if "error" in result:
            status = "✗ ERROR"
            results['errors'] += 1
            print(f"\n✗ {desc} ({elapsed:.2f}s)")
            print(f"  Query: {query}")
            print(f"  Error: {result['error']}")
        else:
            needs_ret = result.get("needs_retrieval", True)
            queries = result.get("queries", [])

            # 判断是否正确
            if expected_query is None:
                # 期望不检索
                correct = not needs_ret
                status = "✓" if correct else "✗"
                if correct:
                    results['correct'] += 1
            else:
                # 期望检索，检查 query 是否包含关键词
                correct = needs_ret and any(expected_query.lower() in q.lower() or q.lower() in expected_query.lower() for q in queries)
                status = "✓" if correct else "✗"
                if correct:
                    results['correct'] += 1
                else:
                    print(f"\n✗ {desc} ({elapsed:.2f}s)")
                    print(f"  Query: {query}")
                    print(f"  expected_query: {expected_query}")
                    print(f"  got queries: {queries}")
                    print(f"  needs_retrieval: {needs_ret}")

            # 统计分类
            cat_key = desc.split('-')[0] + '-' + desc.split('-')[1] if '-' in desc else cat
            if cat_key not in results['by_category']:
                results['by_category'][cat_key] = {'total': 0, 'correct': 0}
            results['by_category'][cat_key]['total'] += 1
            if correct:
                results['by_category'][cat_key]['correct'] += 1

            print(f"\n{status} {desc} ({elapsed:.2f}s)")
            print(f"  Query: {query}")
            print(f"  queries: {queries}")
            print(f"  is_relation_query: {result.get('is_relation_query')}")

    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    print(f"总计: {results['correct']}/{results['total']} 正确 ({results['correct']*100/results['total']:.1f}%)")
    print(f"错误: {results['errors']}")
    print(f"\n按分类统计:")
    for cat, stats in sorted(results['by_category'].items()):
        rate = stats['correct']*100/stats['total'] if stats['total'] > 0 else 0
        print(f"  {cat}: {stats['correct']}/{stats['total']} ({rate:.1f}%)")

    # 计算平均耗时
    print(f"\n注意: 上述耗时包含网络延迟，实际部署时可更准确测量")

if __name__ == "__main__":
    test_siliconflow_qwen()
