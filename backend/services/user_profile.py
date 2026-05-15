"""
用户画像服务 — 从历史行为构建用户偏好向量
冷启动: LLM 根据显式输入推断
迭代: 历史记录加权累积
"""
import json
import os
from services.llm_service import llm_service

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

PROFILE_SYSTEM_PROMPT = """你是一个用户画像分析器。根据用户当前输入和历史行为，构建偏好向量。

输出 JSON:
{
  "consumption_level": "经济/中档/高端",
  "preferred_categories": ["偏好类别"],
  "vibe_preferences": ["氛围偏好"],
  "budget_tolerance": 0-1的预算弹性,
  "pace": "紧凑/适中/悠闲",
  "transport_preference": "步行/骑行/地铁/驾车",
  "persona": "一句话用户画像描述"
}
"""


async def build_profile(intent: dict, history: list = None) -> dict:
    """构建用户画像——冷启动或迭代更新"""
    if not history and not intent.get("explicit_preferences"):
        return _default_profile(intent)

    # 从历史中提取消费偏好
    history_budgets = []
    history_vibes = []
    for h in (history or [])[-10:]:
        pi = h.get("parsed_intent", {})
        if isinstance(pi, str):
            try: pi = json.loads(pi)
            except: continue
        b = pi.get("budget", 0)
        if b: history_budgets.append(b)
        v = pi.get("vibe", "")
        if v: history_vibes.append(v)

    # 消费能力从历史推断
    avg_budget = sum(history_budgets) / len(history_budgets) if history_budgets else intent.get("budget", 500)
    if avg_budget < 200: level = "经济"
    elif avg_budget < 800: level = "中档"
    else: level = "高端"

    return {
        "consumption_level": level,
        "preferred_categories": intent.get("explicit_preferences", []),
        "vibe_preferences": intent.get("implicit_preferences", []) + list(set(history_vibes[-5:])),
        "budget_tolerance": min(1.0, len(history_budgets) / 10),
        "pace": "适中",
        "transport_preference": intent.get("transport", "混合"),
        "persona": f"{level}消费，偏好{intent.get('vibe','休闲')}风格",
    }


def _default_profile(intent: dict) -> dict:
    budget = intent.get("budget", 500)
    level = "经济" if budget < 200 else "中档" if budget < 800 else "高端"
    return {
        "consumption_level": level,
        "preferred_categories": intent.get("explicit_preferences", []),
        "vibe_preferences": intent.get("implicit_preferences", []),
        "budget_tolerance": 0.3,
        "pace": "适中",
        "transport_preference": intent.get("transport", "混合"),
        "persona": f"{level}消费，偏好{intent.get('vibe','休闲')}风格",
    }


def get_user_history(session_id: str, db_session) -> list:
    """从数据库读取用户历史"""
    from database import UserHistory
    records = db_session.query(UserHistory).filter(
        UserHistory.session_id == session_id
    ).order_by(UserHistory.created_at.desc()).limit(20).all()
    return [
        {
            "query_text": r.query_text,
            "parsed_intent": r.parsed_intent,
            "selected_plan": r.selected_plan,
            "feedback": r.feedback,
        }
        for r in records
    ]
