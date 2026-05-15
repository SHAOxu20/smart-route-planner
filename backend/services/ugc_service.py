"""
UGC 语义服务 — 从多平台评价中提取氛围标签、体验关键词
支持小红书/大众点评等公开数据源的标签注入
"""
import json
import os
from services.llm_service import llm_service

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

UGC_EXTRACT_PROMPT = """你是一个场所氛围分析器。根据评价文本提取语义标签。

输出 JSON:
{
  "tags": ["氛围标签1","标签2"],
  "vibe_score": 0-10的氛围感评分,
  "crowd_level": "热门/适中/清静",
  "best_for": ["适合场景1","场景2"],
  "photo_friendly": true/false,
  "summary": "一句话体验总结"
}

标签可选: 拍照出片, 氛围感强, 安静适合聊天, 适合约会, 亲子友好,
高档有面子, 烟火气, 文艺清新, 复古格调, 现代简约, 自然风光,
适合独处, 热闹聚会, 有包间, 景观位, 宠物友好
"""


def load_ugc_reviews() -> list:
    path = os.path.join(DATA_DIR, "ugc_reviews.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


async def extract_semantic_tags(poi_name: str, reviews: list[str]) -> dict:
    """用 LLM 从评价中提取语义标签"""
    if not reviews:
        return {"tags": [], "vibe_score": 5.0, "summary": ""}

    combined = f"场所: {poi_name}\n评价:\n" + "\n".join(f"- {r}" for r in reviews[:5])
    try:
        result = await llm_service.chat(UGC_EXTRACT_PROMPT, combined, temperature=0.4)
        return json.loads(result.strip().replace("```json", "").replace("```", ""))
    except (json.JSONDecodeError, Exception):
        return {"tags": [], "vibe_score": 5.0, "summary": reviews[0][:100] if reviews else ""}


def match_poi_to_user_vibe(poi: dict, user_prefs: list, user_vibe: str) -> float:
    """计算 POI 与用户氛围偏好的匹配度 (0-1)"""
    poi_tags = set(t.lower() for t in poi.get("tags", []))
    pref_tags = set(p.lower() for p in user_prefs)

    if not pref_tags:
        return 0.5

    overlap = poi_tags & pref_tags
    # 精确匹配 + 语义相近匹配
    score = len(overlap) / len(pref_tags)

    # vibe 词模糊匹配
    vibe_map = {
        "浪漫": ["适合约会", "氛围感强", "拍照出片", "景观位"],
        "休闲": ["安静适合聊天", "文艺清新", "烟火气", "自然风光"],
        "商务": ["高档有面子", "有包间", "安静适合聊天", "现代简约"],
        "亲子": ["亲子友好", "互动体验", "宠物友好", "自然风光"],
    }
    related = set(vibe_map.get(user_vibe, []))
    score += 0.2 * len(poi_tags & related) / max(len(related), 1)
    return min(score, 1.0)
