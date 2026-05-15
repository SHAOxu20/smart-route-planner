"""
意图解析服务 — 自由理解用户任意输入，无预设场景限制
"""
import json
import re
from services.llm_service import llm_service

INTENT_SYSTEM_PROMPT = """你是一个出行规划助手。从用户输入中提取结构化信息。

输出 JSON:
{
  "purpose": "用户想去做什么（自由描述，不限分类）",
  "destination": "目标城市或区域",
  "people": 人数(int),
  "budget": 预算上限(元, int),
  "duration_hours": 可用时长(小时, float),
  "explicit_preferences": ["用户明确提到的偏好"],
  "implicit_preferences": ["从语境推断的偏好"],
  "vibe": "整体氛围关键词",
  "weather_concern": true/false,
  "search_keywords": ["用于搜索POI的关键词列表"]
}

要求: 只输出 JSON，不输出其他内容。search_keywords 从用户输入中提取可用于地图搜索的具体词汇。"""


async def parse_intent(user_input: str, user_history: list = None) -> dict:
    """解析用户意图"""
    message = f"用户输入: {user_input}"

    if user_history:
        history_text = _format_history(user_history)
        message += f"\n\n该用户历史行为:\n{history_text}\n请结合历史偏好调整推断。"

    try:
        result = await llm_service.chat(INTENT_SYSTEM_PROMPT, message, temperature=0.3, max_tokens=384)
        intent = json.loads(result.strip().replace("```json", "").replace("```", ""))
        return intent
    except (json.JSONDecodeError, Exception):
        return _extract_intent(user_input)


def _format_history(history: list) -> str:
    if not history:
        return "无历史记录"
    lines = []
    for h in history[-5:]:
        q = h.get("query_text", "")
        p = h.get("parsed_intent", {})
        lines.append(f"- 提问: {q} | 偏好: {p.get('explicit_preferences',[])} | 预算: {p.get('budget','')}")
    return "\n".join(lines)


def _extract_intent(text: str) -> dict:
    """从任意自然语言中提取意图，无预设分类"""

    intent = {
        "purpose": "",
        "destination": "",
        "people": 2,
        "budget": 500,
        "duration_hours": 4.0,
        "explicit_preferences": [],
        "implicit_preferences": [],
        "vibe": "休闲",
        "weather_concern": False,
        "search_keywords": [],
    }

    # —— 人数 ——
    m = re.search(r"(\d+)\s*(个?人|位)", text)
    if m:
        intent["people"] = int(m.group(1))

    # —— 时长 ——
    m = re.search(r"(\d+\.?\d*)\s*(小时|个?钟头|h)", text)
    if m:
        intent["duration_hours"] = float(m.group(1))
    elif "半天" in text:
        intent["duration_hours"] = 4.0
    elif "一天" in text or "整天" in text:
        intent["duration_hours"] = 8.0

    # —— 预算 ——
    m = re.search(r"(\d+)\s*(块|元|¥)", text)
    if m:
        intent["budget"] = int(m.group(1))
    elif any(w in text for w in ["便宜", "省钱", "实惠", "性价比"]):
        intent["budget"] = 200
    elif any(w in text for w in ["贵", "高档", "奢华", "顶级", "最好"]):
        intent["budget"] = 1500

    # —— 氛围 ——
    vibe_map = [
        (["浪漫", "约会", "情侣", "女朋友", "男朋友", "约会"], "浪漫"),
        (["安静", "清净", "放松", "发呆", "看书"], "安静放松"),
        (["热闹", "烟火气", "夜市", "派对", "嗨"], "热闹活力"),
        (["文艺", "格调", "艺术", "设计", "文创"], "文艺格调"),
        (["亲子", "带娃", "孩子", "小朋友", "儿童"], "亲子互动"),
        (["高档", "商务", "应酬", "客户", "招待"], "高端商务"),
        (["自然", "户外", "爬山", "徒步", "公园"], "自然户外"),
    ]
    for keywords, vibe in vibe_map:
        if any(w in text for w in keywords):
            intent["vibe"] = vibe
            intent["implicit_preferences"].append(vibe)
            break

    # —— 显式偏好 ——
    pref_keywords = {
        "拍照": ["拍照", "出片", "打卡", "自拍", "摄影"],
        "美食": ["美食", "好吃", "吃货", "地道", "特色"],
        "咖啡": ["咖啡", "下午茶", "奶茶", "甜品"],
        "文化": ["历史", "文化", "博物", "展览", "古迹"],
        "购物": ["逛街", "购物", "买东西", "商场", "集市"],
        "户外": ["户外", "爬山", "徒步", "骑行", "公园"],
        "网红": ["网红", "热门", "爆火", "排队", "人气"],
        "小众": ["小众", "冷门", "本地人", "秘境", "隐藏"],
    }
    for tag, keywords in pref_keywords.items():
        if any(w in text for w in keywords):
            intent["explicit_preferences"].append(tag)

    # —— 天气 ——
    if any(w in text for w in ["下雨", "雨天", "天气", "晒", "热", "冷"]):
        intent["weather_concern"] = True
        intent["implicit_preferences"].append("室内优先")

    # —— 搜索关键词 ——
    intent["search_keywords"] = _extract_search_keywords(text, intent)

    # —— 目的描述 ——
    intent["purpose"] = _describe_purpose(intent)

    return intent


def _extract_search_keywords(text: str, intent: dict) -> list:
    """从输入中提取高德地图搜索关键词"""
    keywords = set()

    # 从显式偏好生成搜索词
    pref_to_amap = {
        "美食": ["餐厅", "特色菜", "小吃", "火锅", "日料", "烧烤", "海鲜"],
        "咖啡": ["咖啡厅", "茶馆", "甜品店"],
        "文化": ["博物馆", "美术馆", "展览馆", "文化宫"],
        "拍照": ["网红打卡地", "创意园", "特色街区"],
        "户外": ["公园", "风景区", "山", "湖", "步道"],
        "购物": ["商场", "步行街", "夜市"],
        "网红": ["网红店", "人气餐厅", "热门景点"],
        "小众": ["小众景点", "独立书店", "古着店"],
    }

    vibe_to_amap = {
        "浪漫": ["西餐厅", "观景台", "甜品店", "花园"],
        "安静放松": ["茶馆", "书店", "公园", "咖啡厅"],
        "热闹活力": ["夜市", "酒吧", "大排档", "商业街"],
        "文艺格调": ["文创园", "画廊", "独立书店", "咖啡厅"],
        "亲子互动": ["游乐园", "动物园", "科技馆", "公园"],
        "高端商务": ["高档餐厅", "私房菜", "茶楼", "会所"],
        "自然户外": ["风景区", "公园", "山", "湖", "步道"],
    }

    for pref in intent.get("explicit_preferences", []):
        for kw in pref_to_amap.get(pref, [pref]):
            keywords.add(kw)

    for vibe_kw in vibe_to_amap.get(intent.get("vibe", ""), []):
        keywords.add(vibe_kw)

    # 从文本中提取具体词汇
    place_patterns = [
        r"去(.{2,8}?)(?:玩|吃|逛|看|买|住)",
        r"(?:在|到|找)(.{2,8}?)(?:附近|周边|那边)",
    ]
    for pat in place_patterns:
        for m in re.finditer(pat, text):
            word = m.group(1).strip()
            if len(word) >= 2:
                keywords.add(word)

    # 限制数量
    result = list(keywords)[:10]
    if not result:
        result = ["景点", "美食", "咖啡厅"]
    return result


def _describe_purpose(intent: dict) -> str:
    """根据提取的意图生成目的描述"""
    parts = []
    vibe = intent.get("vibe", "")
    prefs = intent.get("explicit_preferences", [])
    if vibe:
        parts.append(vibe)
    if prefs:
        parts.append("、".join(prefs[:3]))
    if not parts:
        parts.append("出行游玩")
    return "，".join(parts)
