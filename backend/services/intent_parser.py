"""
意图解析服务 — 用 LLM 将自然语言转为结构化参数
支持结合用户历史行为做个性化推断
"""
import json
from services.llm_service import llm_service

INTENT_SYSTEM_PROMPT = """你是一个出行意图解析器。将用户的自然语言输入解析为结构化 JSON。

输出 JSON 格式:
{
  "purpose": "游玩/餐饮/商务应酬/购物/日常出行",
  "destination": "区域或地名",
  "people": 人数(int),
  "budget": 总预算上限(元, int),
  "duration_hours": 可用时长(小时, float),
  "explicit_preferences": ["显式偏好列表"],
  "implicit_preferences": ["从语境推断的隐含偏好"],
  "transport": "步行/骑行/地铁/驾车/混合",
  "vibe": "氛围关键词",
  "weather_concern": "是否关注天气 true/false"
}

规则:
- 情侣/约会 → implicit_preferences 补 ["适合情侣","氛围感","拍照出片"]
- 带娃/亲子 → implicit_preferences 补 ["亲子友好","安全","互动体验"]
- 商务/客户 → implicit_preferences 补 ["高档","安静","包间"]
- 提到下雨/天气 → weather_concern = true, 优先室内
- 提到便宜/省钱 → budget 按低档估算
- 提到不想排队 → implicit_preferences 补 ["人少","不用排队"]

只输出 JSON，不输出其他内容。"""


async def parse_intent(user_input: str, user_history: list = None) -> dict:
    """解析用户意图，可选传入历史记录做个性化增强"""
    message = f"用户输入: {user_input}"

    if user_history:
        # 将历史摘要注入 prompt，让 LLM 感知用户偏好
        history_text = _format_history(user_history)
        message += f"\n\n该用户历史行为:\n{history_text}\n请结合历史偏好调整推断。"

    try:
        result = await llm_service.chat(INTENT_SYSTEM_PROMPT, message, temperature=0.3, max_tokens=384)
        intent = json.loads(result.strip().replace("```json", "").replace("```", ""))
        return intent
    except (json.JSONDecodeError, Exception):
        # 回退到基础解析
        return _fallback_parse(user_input)


def _format_history(history: list) -> str:
    """将历史记录格式化为 LLM 可读文本"""
    if not history:
        return "无历史记录"
    lines = []
    for h in history[-5:]:  # 只取最近 5 条
        q = h.get("query_text", "")
        p = h.get("parsed_intent", {})
        lines.append(f"- 提问: {q} | 目的: {p.get('purpose','')} | 偏好: {p.get('explicit_preferences',[])} | 预算: {p.get('budget','')}")
    return "\n".join(lines)


def _fallback_parse(user_input: str) -> dict:
    """无 LLM 时的规则兜底"""
    text = user_input.lower()
    intent = {
        "purpose": "游玩",
        "destination": "",
        "people": 2,
        "budget": 500,
        "duration_hours": 4.0,
        "explicit_preferences": [],
        "implicit_preferences": [],
        "transport": "混合",
        "vibe": "休闲",
        "weather_concern": False,
    }

    if any(w in text for w in ["约会", "女朋友", "男朋友", "情侣"]):
        intent["purpose"] = "约会"
        intent["implicit_preferences"] = ["适合情侣", "氛围感", "拍照出片"]
        intent["vibe"] = "浪漫"
        intent["budget"] = 600
    elif any(w in text for w in ["亲子", "带娃", "孩子", "小朋友"]):
        intent["purpose"] = "亲子"
        intent["implicit_preferences"] = ["亲子友好", "安全", "互动体验"]
    elif any(w in text for w in ["商务", "客户", "应酬", "开会"]):
        intent["purpose"] = "商务应酬"
        intent["implicit_preferences"] = ["高档", "安静", "包间"]
        intent["budget"] = 1500

    if any(w in text for w in ["拍照", "出片", "打卡"]):
        intent["explicit_preferences"].append("拍照")
    if any(w in text for w in ["便宜", "省钱", "实惠", "性价比"]):
        intent["budget"] = 200
    if any(w in text for w in ["下雨", "雨天", "天气"]):
        intent["weather_concern"] = True
        intent["implicit_preferences"].append("室内优先")
    if any(w in text for w in ["排队", "人多", "网红"]):
        intent["implicit_preferences"].append("人少不用排队")

    return intent
