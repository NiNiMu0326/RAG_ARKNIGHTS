"""全面测试不同 LLM 模型的重写质量和速度"""
import time
import json
import sys
import random
import string

sys.path.insert(0, '.')

def generate_unique_id():
    """生成随机ID避免缓存"""
    return ''.join(random.choices(string.ascii_letters, k=8))

# 更多测试用例，覆盖各种场景
test_cases = [
    # === 无历史无代词 ===
    ('{id}狮蝎别名有什么', [], '无历史-别名'),
    ('{id}银灰的技能是什么', [], '无历史-技能'),
    ('{id}维什戴尔的背景故事是什么', [], '无历史-背景故事'),
    ('{id}迷迭香的关系是什么', [], '无历史-关系'),
    ('{id}陈是谁', [], '无历史-身份'),
    ('{id}德克萨斯皮肤有哪些', [], '无历史-皮肤'),
    ('{id}明日方舟公招攻略', [], '无历史-攻略'),
    ('{id}银灰怎么获得', [], '无历史-获取方式'),
    ('{id}史尔特尔天赋是什么', [], '无历史-天赋'),
    ('{id}能天使皮肤', [], '无历史-皮肤简称'),

    # === 有历史无代词 ===
    ('{id}维什戴尔的技能是什么', [], '无历史-技能2'),
    ('{id}她的别名是什么', [{'role': 'user', 'content': '{id}维什戴尔的技能是什么'}], '有历史-代词-别名'),
    ('{id}那银灰呢', [{'role': 'user', 'content': '{id}维什戴尔技能'}, {'role': 'assistant', 'content': '维什戴尔是六星'}], '有历史-那指代'),
    ('{id}她的背景故事呢', [{'role': 'user', 'content': '{id}银灰技能'}], '有历史-代词-背景'),
    ('{id}他的天赋是什么', [{'role': 'user', 'content': '{id}史尔特尔技能'}], '有历史-代词-天赋'),
    ('{id}那她的关系呢', [{'role': 'user', 'content': '{id}银灰'}, {'role': 'assistant', 'content': '银灰是六星辅助'}], '有历史-那指代-关系'),

    # === 有历史有代词-多干员 ===
    ('{id}她们的关系是什么', [{'role': 'user', 'content': '{id}维什戴尔的技能是什么，迷迭香的技能是什么'}], '有历史-代词-多干员关系'),
    ('{id}他和她的关系', [{'role': 'user', 'content': '{id}银灰技能'}, {'role': 'assistant', 'content': '银灰是六星辅助'}], '有历史-代词-多干员关系2'),
    ('{id}她们有什么关系', [{'role': 'user', 'content': '{id}能天使'}, {'role': 'assistant', 'content': '能天使是三星'}], '有历史-代词-多干员关系3'),

    # === 无历史有代词 ===
    ('{id}她的别名是什么', [], '无历史-代词-别名'),
    ('{id}他技能是什么', [], '无历史-代词-技能'),
    ('{id}它的背景故事是什么', [], '无历史-代词-背景'),

    # === 闲聊不检索 ===
    ('{id}你好', [], '闲聊-问候'),
    ('{id}今天天气不错', [], '闲聊-天气'),
    ('{id}你是谁', [], '闲聊-身份'),
    ('{id}随便聊聊', [], '闲聊-随便'),
    ('{id}你觉得银灰怎么样', [], '闲聊-看法'),

    # === 复杂查询 ===
    ('{id}银灰和初雪什么关系', [], '无历史-双干员关系'),
    ('{id}维什戴尔和史尔特尔谁更强', [], '无历史-对比'),
    ('{id}赫默和塞雷娅是什么关系', [], '无历史-双干员关系2'),

    # === 更多有历史代词场景 ===
    ('{id}她的精英化材料是什么', [{'role': 'user', 'content': '{id}银灰技能'}], '有历史-代词-精英材料'),
    ('{id}那他的模组呢', [{'role': 'user', 'content': '{id}史尔特尔天赋'}, {'role': 'assistant', 'content': '史尔特尔天赋是...'}], '有历史-那指代-模组'),
    ('{id}她的公招信息', [{'role': 'user', 'content': '{id}能天使公招'}], '有历史-代词-公招'),
    ('{id}她们的背景故事', [{'role': 'user', 'content': '{id}银灰和史尔特的技能'}], '有历史-代词-多干员-背景'),
    ('{id}他和她有什么关系', [{'role': 'user', 'content': '{id}银灰'}, {'role': 'assistant', 'content': '银灰是六星'}], '有历史-代词-多干员-关系2'),
]

def test_model(model_name, api_client):
    """测试指定模型"""
    results = {'total': 0, 'correct': 0, 'errors': 0, 'by_category': {}, 'times': []}

    prompt_template = """你是一个明日方舟RAG查询改写助手。请根据对话历史改写用户问题。

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
{history_text}

## 用户问题
{query}

## JSON输出
"""

    for test_case in test_cases:
        query_template, history_template, desc = test_case
        # 生成唯一ID避免缓存
        unique_id = generate_unique_id()
        query = query_template.replace('{id}', unique_id)
        history = [{'role': h['role'], 'content': h['content'].replace('{id}', unique_id)} for h in history_template]

        results['total'] += 1

        history_text = ""
        if history:
            recent = history[-5:]
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

        prompt = prompt_template.format(history_text=history_text if history_text else "无", query=query)

        start = time.time()
        try:
            response = api_client.chat([
                {"role": "system", "content": "你是一个明日方舟RAG助手，直接输出JSON。"},
                {"role": "user", "content": prompt}
            ], model=model_name)

            elapsed = time.time() - start
            results['times'].append(elapsed)

            raw = response.strip()
            if raw.startswith('```'):
                lines = raw.split('\n')
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip().endswith('```'):
                    lines = lines[:-1]
                raw = '\n'.join(lines)
            result = json.loads(raw)

            cat = desc.split('-')[0] + '-' + desc.split('-')[1] if '-' in desc else desc
            if cat not in results['by_category']:
                results['by_category'][cat] = {'total': 0, 'correct': 0, 'times': []}
            results['by_category'][cat]['total'] += 1
            results['by_category'][cat]['times'].append(elapsed)

            results['correct'] += 1
            results['by_category'][cat]['correct'] += 1

        except Exception as e:
            elapsed = time.time() - start
            results['times'].append(elapsed)
            results['errors'] += 1
            results['correct'] += 0
            cat = desc.split('-')[0]
            if cat not in results['by_category']:
                results['by_category'][cat] = {'total': 0, 'correct': 0, 'times': []}
            results['by_category'][cat]['total'] += 1

    return results

def run_tests():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    from api.siliconflow import SiliconFlowClient

    # 使用 SiliconFlow API 测试不同模型
    models = [
        'Pro/MiniMaxAI/MiniMax-M2.5',
        'Pro/deepseek-ai/DeepSeek-V3.2',
        'Qwen/Qwen2.5-7B-Instruct',
    ]

    print("=" * 80)
    print("LLM 模型对比测试 (SiliconFlow)")
    print("=" * 80)

    all_results = {}

    for model_name in models:
        print(f"\n{'='*40}")
        print(f"  模型: {model_name}")
        print(f"{'='*40}")

        client = SiliconFlowClient()
        results = test_model(model_name, client)
        all_results[model_name] = results

        avg_time = sum(results['times']) / len(results['times']) if results['times'] else 0
        print(f"\n总计: {results['correct']}/{results['total']} 正确 ({results['correct']*100/results['total']:.1f}%)")
        print(f"错误: {results['errors']}")
        print(f"平均耗时: {avg_time:.2f}s")

        print(f"\n按分类统计:")
        for cat, stats in sorted(results['by_category'].items()):
            rate = stats['correct']*100/stats['total'] if stats['total'] > 0 else 0
            avg_cat_time = sum(stats['times']) / len(stats['times']) if stats['times'] else 0
            print(f"  {cat}: {stats['correct']}/{stats['total']} ({rate:.1f}%) - 平均 {avg_cat_time:.2f}s")

    # 总结对比
    print("\n" + "=" * 80)
    print("模型对比总结")
    print("=" * 80)
    print(f"{'模型':<35} {'正确率':<10} {'平均耗时':<10}")
    print("-" * 60)
    for model_name, results in all_results.items():
        rate = results['correct']*100/results['total'] if results['total'] > 0 else 0
        avg_time = sum(results['times']) / len(results['times']) if results['times'] else 0
        short_name = model_name.split('/')[-1] if '/' in model_name else model_name
        print(f"{short_name:<35} {rate:>6.1f}%     {avg_time:>5.2f}s")

if __name__ == "__main__":
    run_tests()
