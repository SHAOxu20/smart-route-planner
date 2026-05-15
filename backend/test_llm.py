import asyncio, json, sys, os
os.chdir(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(__file__))
from services.llm_service import llm_service

async def test():
    # 测试意图解析
    print("=== 测试意图解析 ===")
    result = await llm_service.chat(
        '将用户输入解析为出行意图，仅输出 JSON。',
        '周末和女朋友出去玩，想拍照不要太贵，预算500',
        temperature=0.3
    )
    print(result[:600])
    print()

    # 测试路线描述
    print("=== 测试路线描述 ===")
    plan_data = {
        "weather_advice": "今日多云24°C，适合出行",
        "plan": {
            "label": "体验优先",
            "stops": [
                {"arrival_time": "14:00", "name": "M50创意园", "category": "景点", "cost": 0, "tags": ["拍照出片","文艺清新"]},
                {"arrival_time": "16:00", "name": "Seesaw Coffee", "category": "休闲", "cost": 40, "tags": ["安静","文艺"]},
                {"arrival_time": "18:00", "name": "老吉士酒家", "category": "餐饮", "cost": 180, "tags": ["适合约会","老字号"]},
            ],
            "total_cost": 220, "total_time_minutes": 300,
        }
    }
    result2 = await llm_service.chat(
        '将路线方案转化为自然语言描述，语气温暖自然。',
        json.dumps(plan_data, ensure_ascii=False),
        temperature=0.8
    )
    print(result2[:800])

asyncio.run(test())
