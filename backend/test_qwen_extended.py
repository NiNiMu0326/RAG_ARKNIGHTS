"""扩展测试 - 100+ 测试用例验证 Qwen 准确率"""
import time
import json
import sys
import random
import string

sys.path.insert(0, '.')

def generate_unique_id():
    return ''.join(random.choices(string.ascii_letters, k=8))

# 100+ 测试用例
test_cases = [
    # === 无历史无代词-技能 ===
    ('{id}银灰技能是什么', [], True, '技能'),
    ('{id}银灰的技能是什么', [], True, '技能'),
    ('{id}史尔特尔技能', [], True, '技能简称'),
    ('{id}维什戴尔技能', [], True, '技能简称'),
    ('{id}能天使技能是什么', [], True, '技能'),
    ('{id}艾雅法拉火山羊技能', [], True, '技能'),
    ('{id}小羊技能', [], True, '技能别名'),

    # === 无历史无代词-别名 ===
    ('{id}狮蝎别名有什么', [], True, '别名'),
    ('{id}银灰别名', [], True, '别名'),
    ('{id}德克萨斯别名', [], True, '别名'),
    ('{id}陈别名是什么', [], True, '别名'),
    ('{id}老陈别名', [], True, '别名'),
    ('{id}银老板别名', [], True, '别名'),

    # === 无历史无代词-背景故事 ===
    ('{id}银灰背景故事', [], True, '背景故事'),
    ('{id}维什戴尔背景故事是什么', [], True, '背景故事'),
    ('{id}迷迭香背景', [], True, '背景'),
    ('{id}陈的背景故事是什么', [], True, '背景故事'),

    # === 无历史无代词-关系 ===
    ('{id}银灰和初雪什么关系', [], True, '双干员关系'),
    ('{id}银灰初雪关系', [], True, '双干员关系'),
    ('{id}维什戴尔和史尔特尔关系', [], True, '双干员关系'),
    ('{id}赫默塞雷娅关系', [], True, '双干员关系'),
    ('{id}能天使和德克萨斯什么关系', [], True, '双干员关系'),

    # === 无历史无代词-天赋 ===
    ('{id}史尔特尔天赋是什么', [], True, '天赋'),
    ('{id}银灰天赋', [], True, '天赋'),
    ('{id}维什戴尔天赋', [], True, '天赋'),

    # === 无历史无代词-获取方式 ===
    ('{id}银灰怎么获得', [], True, '获取方式'),
    ('{id}银灰如何获得', [], True, '获取方式'),
    ('{id}史尔特尔获取方式', [], True, '获取方式'),
    ('{id}怎么获得维什戴尔', [], True, '获取方式'),

    # === 无历史无代词-精英化 ===
    ('{id}银灰精英化材料', [], True, '精英材料'),
    ('{id}史尔特尔精英二材料', [], True, '精英材料'),
    ('{id}银灰精英化攻略', [], True, '精英攻略'),

    # === 无历史无代词-模组 ===
    ('{id}银灰模组', [], True, '模组'),
    ('{id}史尔特尔模组是什么', [], True, '模组'),

    # === 无历史无代词-公招 ===
    ('{id}公招攻略', [], True, '公招'),
    ('{id}公招技巧', [], True, '公招'),
    ('{id}怎么公招到六星', [], True, '公招'),

    # === 无历史无代词-寻访 ===
    ('{id}寻访技巧', [], True, '寻访'),
    ('{id}抽卡攻略', [], True, '寻访'),

    # === 无历史无代词-皮肤 ===
    ('{id}银灰皮肤', [], True, '皮肤'),
    ('{id}银灰皮肤有哪些', [], True, '皮肤'),
    ('{id}能天使新皮肤', [], True, '皮肤'),

    # === 无历史无代词-立绘 ===
    ('{id}银灰立绘', [], True, '立绘'),
    ('{id}能天使立绘', [], True, '立绘'),

    # === 无历史无代词-配音/CV ===
    ('{id}银灰声优', [], True, '声优'),
    ('{id}银灰配音', [], True, '配音'),
    ('{id}能天使cv', [], True, 'CV'),

    # === 无历史无代词-画师 ===
    ('{id}银灰画师', [], True, '画师'),
    ('{id}能天使人设', [], True, '人设'),

    # === 无历史无代词-职业 ===
    ('{id}银灰职业', [], True, '职业'),
    ('{id}史尔特尔职业', [], True, '职业'),
    ('{id}银灰阵营', [], True, '阵营'),

    # === 无历史无代词-强度/攻略 ===
    ('{id}银灰强度', [], True, '强度'),
    ('{id}史尔特尔强不强', [], True, '强度'),
    ('{id}银灰攻略', [], True, '攻略'),
    ('{id}危机合约攻略', [], True, '攻略'),

    # === 无历史无代词-身份 ===
    ('{id}陈是谁', [], True, '身份'),
    ('{id}银灰是谁', [], True, '身份'),
    ('{id}史尔特尔是谁', [], True, '身份'),

    # === 无历史有代词 ===
    ('{id}她的别名是什么', [], True, '无历史代词'),
    ('{id}他的技能', [], True, '无历史代词'),
    ('{id}它的背景故事', [], True, '无历史代词'),
    ('{id}这干员技能', [], True, '无历史代词'),
    ('{id}那干员天赋', [], True, '无历史代词'),

    # === 有历史-代词引用 ===
    ('{id}她的别名', [{'role': 'user', 'content': '{id}银灰技能'}], True, '有历史代词'),
    ('{id}他的天赋是什么', [{'role': 'user', 'content': '{id}史尔特尔技能'}], True, '有历史代词'),
    ('{id}那银灰呢', [{'role': 'user', 'content': '{id}维什戴尔技能'}], True, '那指代'),
    ('{id}那她的背景呢', [{'role': 'user', 'content': '{id}银灰技能'}, {'role': 'assistant', 'content': '银灰是六星'}], True, '那指代'),
    ('{id}他的精英材料', [{'role': 'user', 'content': '{id}能天使技能'}], True, '有历史代词'),
    ('{id}她的皮肤', [{'role': 'user', 'content': '{id}德克萨斯皮肤'}], True, '有历史代词'),
    ('{id}它的获取方式', [{'role': 'user', 'content': '{id}小羊技能'}], True, '有历史代词'),

    # === 有历史-多干员代词 ===
    ('{id}她们关系是什么', [{'role': 'user', 'content': '{id}银灰和史尔特尔技能'}], True, '多干员代词'),
    ('{id}他和她的关系', [{'role': 'user', 'content': '{id}银灰技能'}, {'role': 'assistant', 'content': '银灰是六星'}], True, '多干员代词'),
    ('{id}她们有什么关系', [{'role': 'user', 'content': '{id}能天使和德克萨斯'}], True, '多干员代词'),

    # === 有历史-非代词简单引用 ===
    ('{id}银灰呢', [{'role': 'user', 'content': '{id}维什戴尔技能'}], True, '非代词引用'),
    ('{id}那银灰', [{'role': 'user', 'content': '{id}史尔特尔天赋'}], True, '非代词引用'),
    ('{id}还有呢', [{'role': 'user', 'content': '{id}银灰技能'}], True, '非代词引用'),
    ('{id}继续说', [{'role': 'user', 'content': '{id}银灰背景故事'}], True, '非代词引用'),

    # === 闲聊-问候 ===
    ('{id}你好', [], False, '闲聊'),
    ('{id}早上好', [], False, '闲聊'),
    ('{id}晚上好', [], False, '闲聊'),

    # === 闲聊-身份 ===
    ('{id}你是谁', [], False, '闲聊身份'),
    ('{id}你是干什么的', [], False, '闲聊身份'),
    ('{id}你能做什么', [], False, '闲聊'),

    # === 闲聊-天气/日常 ===
    ('{id}今天天气不错', [], False, '闲聊天气'),
    ('{id}你好吗', [], False, '闲聊'),
    ('{id}最近怎么样', [], False, '闲聊'),

    # === 闲聊-看法 ===
    ('{id}你觉得银灰怎么样', [], False, '闲聊看法'),
    ('{id}银灰好玩吗', [], False, '闲聊'),
    ('{id}明日方舟好玩吗', [], False, '闲聊'),

    # === 闲聊-随便聊聊 ===
    ('{id}随便聊聊', [], False, '闲聊随便'),
    ('{id}聊聊天', [], False, '闲聊'),
    ('{id}讲个笑话', [], False, '闲聊'),

    # === 不确定类型 ===
    ('{id}什么是源石', [], True, '知识'),
    ('{id}理智液有什么用', [], True, '知识'),
    ('{id}剿灭作战奖励', [], True, '知识'),
    ('{id}龙门币怎么获得', [], True, '知识'),
    ('{id}芯片怎么获得', [], True, '知识'),
]

def test_qwen():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    from api.siliconflow import SiliconFlowClient
    client = SiliconFlowClient()

    results = {
        'total': 0,
        'correct': 0,
        'errors': 0,
        'by_category': {},
        'wrong_cases': []
    }

    prompt_template = """你是一个明日方舟RAG查询改写助手。

## 任务
1. 判断是否需要检索知识库（需要：干员信息/剧情/攻略等；不需要：闲聊/问候/自我回答等）
2. 如果需要检索，将问题改写为简短关键词组合，如 "银灰 技能"
3. 如果不需要检索，返回 needs_retrieval=false

## 判断标准
需要检索：干员属性、技能、天赋、关系、背景、获取方式、攻略等具体信息
不需要检索：问候、自我介绍、天气闲聊、询问看法等

## 输出格式（纯JSON）
{{"needs_retrieval": true/false, "queries": ["关键词"], "is_relation_query": true/false}}

## 对话历史
{history_text}

## 用户问题
{query}

## JSON输出
"""

    for query_template, history_template, expected_retrieval, category in test_cases:
        unique_id = generate_unique_id()
        query = query_template.replace('{id}', unique_id)
        history = [{'role': h['role'], 'content': h['content'].replace('{id}', unique_id)} for h in history_template]

        results['total'] += 1

        history_text = ""
        if history:
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-5:]])

        prompt = prompt_template.format(history_text=history_text if history_text else "无", query=query)

        start = time.time()
        try:
            response = client.chat([
                {"role": "system", "content": "直接输出JSON。"},
                {"role": "user", "content": prompt}
            ], model="Qwen/Qwen2.5-7B-Instruct")

            elapsed = time.time() - start

            raw = response.strip()
            if raw.startswith('```'):
                lines = raw.split('\n')
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip().endswith('```'):
                    lines = lines[:-1]
                raw = '\n'.join(lines)
            result = json.loads(raw)

            needs_ret = result.get("needs_retrieval", True)

            if needs_ret == expected_retrieval:
                results['correct'] += 1
            else:
                results['wrong_cases'].append({
                    'query': query,
                    'category': category,
                    'expected': expected_retrieval,
                    'got': needs_ret,
                    'queries': result.get('queries', []),
                    'elapsed': elapsed
                })

            if category not in results['by_category']:
                results['by_category'][category] = {'total': 0, 'correct': 0}
            results['by_category'][category]['total'] += 1
            if needs_ret == expected_retrieval:
                results['by_category'][category]['correct'] += 1

        except Exception as e:
            elapsed = time.time() - start
            results['errors'] += 1
            results['wrong_cases'].append({
                'query': query,
                'category': category,
                'expected': expected_retrieval,
                'got': 'ERROR',
                'error': str(e)[:50],
                'elapsed': elapsed
            })

    return results

def main():
    print("=" * 80)
    print("Qwen 扩展测试 (100+ 测试用例)")
    print("=" * 80)

    results = test_qwen()

    print(f"\n总计: {results['correct']}/{results['total']} 正确 ({results['correct']*100/results['total']:.1f}%)")
    print(f"错误: {results['errors']}")

    print(f"\n按分类统计:")
    for cat, stats in sorted(results['by_category'].items(), key=lambda x: x[1]['correct']/max(1,x[1]['total']), reverse=True):
        rate = stats['correct']*100/stats['total'] if stats['total'] > 0 else 0
        print(f"  {cat}: {stats['correct']}/{stats['total']} ({rate:.1f}%)")

    if results['wrong_cases']:
        print(f"\n错误详情 ({len(results['wrong_cases'])} 个):")
        for i, case in enumerate(results['wrong_cases'][:20], 1):
            print(f"\n{i}. [{case['category']}] {case['query']}")
            print(f"   期望 needs_retrieval: {case['expected']}, 实际: {case['got']}")
            print(f"   queries: {case.get('queries', case.get('error'))}")
            print(f"   耗时: {case['elapsed']:.2f}s")
        if len(results['wrong_cases']) > 20:
            print(f"\n... 还有 {len(results['wrong_cases']) - 20} 个错误")

if __name__ == "__main__":
    main()
