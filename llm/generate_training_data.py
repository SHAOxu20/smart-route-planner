"""
从 POI/UGC/场景数据生成微调训练集
输出 Alpaca 格式，可用于 QLoRA fine-tuning
"""
import json
import os
import random

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "data")
OUTPUT_DIR = os.path.dirname(__file__)


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {} if name.endswith(".json") else []


def gen_intent_parsing_samples() -> list:
    """生成意图解析训练样本"""
    samples = []

    # 约会场景
    dating_inputs = [
        "周末和女朋友出去玩，想去有氛围感的地方",
        "想找个适合约会的地方，拍照好看，不要太贵",
        "和男朋友约会，想吃顿好的，最好有夜景",
        "第一次约会，去哪里比较合适？安静一点的",
        "纪念日和女朋友出去，预算800左右",
    ]
    for q in dating_inputs:
        samples.append({
            "instruction": "将用户输入解析为出行意图 JSON",
            "input": q,
            "output": json.dumps({
                "purpose": "约会", "destination": "上海市中心", "people": 2,
                "budget": 600, "duration_hours": 5.0,
                "explicit_preferences": ["拍照", "氛围感"],
                "implicit_preferences": ["适合情侣", "安静", "景观位"],
                "transport": "步行+地铁", "vibe": "浪漫", "weather_concern": False,
            }, ensure_ascii=False),
        })

    # 亲子场景
    family_inputs = [
        "带5岁小朋友出去玩一天，最好能学点东西",
        "周末遛娃去哪儿？要安全，室内室外都行",
        "带娃出去玩，有没有科普类的场所推荐",
        "亲子一日游，小朋友喜欢动物和恐龙",
    ]
    for q in family_inputs:
        samples.append({
            "instruction": "将用户输入解析为出行意图 JSON",
            "input": q,
            "output": json.dumps({
                "purpose": "亲子", "destination": "上海市中心", "people": 3,
                "budget": 400, "duration_hours": 6.0,
                "explicit_preferences": ["亲子友好", "互动体验"],
                "implicit_preferences": ["安全", "科普教育", "室内"],
                "transport": "驾车", "vibe": "亲子", "weather_concern": True,
            }, ensure_ascii=False),
        })

    # 商务场景
    business_inputs = [
        "请客户吃饭，环境要好，最好有包间",
        "商务宴请，人均500左右，上海哪里合适",
        "和重要客户见面，需要高档安静的餐厅",
    ]
    for q in business_inputs:
        samples.append({
            "instruction": "将用户输入解析为出行意图 JSON",
            "input": q,
            "output": json.dumps({
                "purpose": "商务应酬", "destination": "上海市中心", "people": 4,
                "budget": 2000, "duration_hours": 3.0,
                "explicit_preferences": ["高档", "有包间"],
                "implicit_preferences": ["安静", "面子", "好停车"],
                "transport": "驾车", "vibe": "商务", "weather_concern": False,
            }, ensure_ascii=False),
        })

    # 雨天场景
    samples.append({
        "instruction": "将用户输入解析为出行意图 JSON",
        "input": "下雨了，想出去玩但是不想淋雨，有什么室内推荐",
        "output": json.dumps({
            "purpose": "游玩", "destination": "上海市中心", "people": 2,
            "budget": 400, "duration_hours": 4.0,
            "explicit_preferences": ["室内", "拍照"],
            "implicit_preferences": ["室内优先", "不怕下雨"],
            "transport": "地铁", "vibe": "休闲", "weather_concern": True,
        }, ensure_ascii=False),
    })

    return samples


def gen_route_description_samples() -> list:
    """生成路线描述训练样本"""
    pois = load_json("poi_seed.json")
    if not pois:
        return []

    samples = []

    # 约会路线描述
    samples.append({
        "instruction": "将路线方案转化为自然语言描述",
        "input": json.dumps({
            "weather_advice": "今日多云，温度24°C，适合出行。",
            "plan": {
                "label": "体验优先",
                "stops": [
                    {"arrival_time": "14:00", "name": "M50创意园", "category": "景点",
                     "cost": 0, "tags": ["拍照出片", "文艺清新", "免费"], "travel_from_prev": "起点"},
                    {"arrival_time": "16:00", "name": "%Arabica咖啡(武康路店)", "category": "休闲",
                     "cost": 45, "tags": ["文艺清新", "适合独处", "拍照出片"], "travel_from_prev": "步行5分钟"},
                    {"arrival_time": "18:00", "name": "老吉士酒家", "category": "餐饮",
                     "cost": 180, "tags": ["烟火气", "适合约会", "老字号"], "travel_from_prev": "步行8分钟"},
                ],
                "total_cost": 225, "total_time_minutes": 300,
            },
        }, ensure_ascii=False),
        "output": (
            "今日多云，温度舒适，很适合出行。为你规划了一条文艺约会路线：\n\n"
            "14:00 M50创意园，工业风艺术园区，画廊和涂鸦墙很出片，免门票随便逛，下午光线最好。\n\n"
            "16:00 步行5分钟到%Arabica咖啡，日系极简风咖啡店，窗边位置安静舒服，适合坐下来聊聊天，人均45。\n\n"
            "18:00 步行8分钟到老吉士酒家，上海本帮菜天花板，红烧肉必点，灯光暗暗的氛围很好，适合约会，人均180。\n\n"
            "全程步行范围，无需打车。总预算约225元/人，节奏悠闲不赶。约会愉快！"
        ),
    })

    # 亲子路线描述
    samples.append({
        "instruction": "将路线方案转化为自然语言描述",
        "input": json.dumps({
            "weather_advice": "今日有小雨，建议优先室内活动，记得带伞。",
            "plan": {
                "label": "亲子优选",
                "stops": [
                    {"arrival_time": "10:00", "name": "上海自然博物馆", "category": "景点",
                     "cost": 30, "tags": ["亲子友好", "互动体验", "室内", "科普"], "travel_from_prev": "起点"},
                    {"arrival_time": "13:00", "name": "裕兴记", "category": "餐饮",
                     "cost": 60, "tags": ["性价比", "老字号", "烟火气"], "travel_from_prev": "步行10分钟"},
                ],
                "total_cost": 90, "total_time_minutes": 240,
            },
        }, ensure_ascii=False),
        "output": (
            "今日有小雨，不过没关系，为你规划的全室内路线，记得带伞哦。\n\n"
            "10:00 上海自然博物馆，国内最好的自然博物馆之一，恐龙骨架超震撼，小朋友看到不肯走，30元门票超值。\n\n"
            "13:00 步行10分钟到裕兴记，老字号苏式面馆，秃黄油面一绝，人均60吃到满足。\n\n"
            "轻松的半日游，总花费不到100元/人，室内不怕雨，遛娃无压力。"
        ),
    })

    # 性价比路线
    samples.append({
        "instruction": "将路线方案转化为自然语言描述",
        "input": json.dumps({
            "weather_advice": "今日晴天，温度25°C，非常适合户外。",
            "plan": {
                "label": "性价比之选",
                "stops": [
                    {"arrival_time": "11:00", "name": "武康大楼", "category": "景点",
                     "cost": 0, "tags": ["拍照出片", "复古格调", "网红打卡", "免费"], "travel_from_prev": "起点"},
                    {"arrival_time": "12:30", "name": "沪西老弄堂面馆", "category": "餐饮",
                     "cost": 40, "tags": ["烟火气", "性价比", "老字号", "地道"], "travel_from_prev": "步行12分钟"},
                    {"arrival_time": "14:00", "name": "Seesaw Coffee(愚园路店)", "category": "休闲",
                     "cost": 40, "tags": ["安静适合聊天", "文艺清新"], "travel_from_prev": "步行10分钟"},
                ],
                "total_cost": 80, "total_time_minutes": 200,
            },
        }, ensure_ascii=False),
        "output": (
            "今日阳光正好，适合出来走走。为你规划了一条高性价比路线：\n\n"
            "11:00 武康大楼打卡，上海经典地标，拍照很出片，免费。\n\n"
            "12:30 步行12分钟到沪西老弄堂面馆，开了30年的本帮面馆，辣肉面一绝，人均40吃到撑。\n\n"
            "14:00 步行10分钟到Seesaw Coffee，安静舒服，喝杯冷萃歇歇脚，人均40。\n\n"
            "全程步行+地铁，总花费不到80元/人，好吃好逛不贵。"
        ),
    })

    return samples


def gen_poi_tagging_samples() -> list:
    """生成 POI 标签识别训练样本"""
    reviews = load_json("ugc_reviews.json")
    samples = []

    for item in reviews:
        poi_id = item.get("poi_id", "")
        review_list = item.get("reviews", [])
        if not review_list:
            continue

        # 找对应的标签
        tags_data = load_json("ugc_tags.json")
        tags = tags_data.get(poi_id, {}).get("tags", [])

        samples.append({
            "instruction": "根据用户评价提取场所的语义标签和氛围关键词",
            "input": "\n".join(f"- {r}" for r in review_list[:3]),
            "output": json.dumps({
                "tags": tags[:5],
                "summary": review_list[0][:100],
            }, ensure_ascii=False),
        })

    return samples


def gen_adjust_samples() -> list:
    """生成动态调整训练样本"""
    return [
        {
            "instruction": "用户对路线提出调整需求，修改出行参数",
            "input": "太贵了，有没有便宜点的方案",
            "output": json.dumps({
                "action": "reduce_budget",
                "budget_multiplier": 0.6,
                "reason": "用户反馈价格超出预期，切换到性价比方案",
            }, ensure_ascii=False),
        },
        {
            "instruction": "用户对路线提出调整需求，修改出行参数",
            "input": "加个甜品店，逛完想坐下吃点甜的",
            "output": json.dumps({
                "action": "add_poi",
                "category": "甜品/咖啡",
                "insert_after": "景点",
                "priority": "高评分+氛围好",
            }, ensure_ascii=False),
        },
        {
            "instruction": "用户对路线提出调整需求，修改出行参数",
            "input": "时间来不及了，能跳过一些地方吗",
            "output": json.dumps({
                "action": "shorten_route",
                "duration_multiplier": 0.6,
                "strategy": "删除非核心POI，保留最高匹配度场所",
            }, ensure_ascii=False),
        },
    ]


def main():
    all_samples = []
    all_samples.extend(gen_intent_parsing_samples())
    all_samples.extend(gen_route_description_samples())
    all_samples.extend(gen_poi_tagging_samples())
    all_samples.extend(gen_adjust_samples())

    # 保存 Alpaca 格式 (通用微调)
    alpaca_path = os.path.join(OUTPUT_DIR, "training_data_alpaca.json")
    with open(alpaca_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, ensure_ascii=False, indent=2)

    # 保存 ShareGPT 格式 (Axolotl / Unsloth)
    sharegpt = []
    for s in all_samples:
        sharegpt.append({
            "conversations": [
                {"from": "system", "value": "你是 LocalSmartRoute，专精于本地路线规划的 AI 助手。"},
                {"from": "human", "value": f"{s['instruction']}\n\n{s['input']}"},
                {"from": "gpt", "value": s["output"]},
            ],
        })

    sharegpt_path = os.path.join(OUTPUT_DIR, "training_data_sharegpt.json")
    with open(sharegpt_path, "w", encoding="utf-8") as f:
        json.dump(sharegpt, f, ensure_ascii=False, indent=2)

    print(f"生成 {len(all_samples)} 条训练样本")
    print(f"  Alpaca 格式: {alpaca_path}")
    print(f"  ShareGPT 格式: {sharegpt_path}")


if __name__ == "__main__":
    main()
