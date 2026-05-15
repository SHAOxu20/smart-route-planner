"""
路线规划引擎 — 贪心 + 规则模板生成 A/B/C 三套方案
包含空间剪枝、时间约束检查、多方案差异化策略
"""
import math
import random
from services.ugc_service import match_poi_to_user_vibe
from services.llm_service import llm_service

ROUTE_DESCRIPTION_PROMPT = """你是一个旅行规划师。将路线方案转化为温暖、可执行的自然语言描述。

要求:
- 第一句说明天气和整体建议
- 每个节点包含: 时间、场所名、特色、费用、承接语
- 结尾给出总预算和温馨提示
- 语气温暖但不啰嗦，像朋友推荐

仅输出路线描述文本。"""


def haversine(lat1, lng1, lat2, lng2):
    """计算两点间距离 (km)"""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def time_to_minutes(t: str) -> tuple:
    """解析营业时间字符串为 (open_min, close_min)，支持逗号分隔的多段"""
    if not t or "-" not in t:
        return (0, 1440)
    try:
        # 处理逗号分隔的多段时间，只取第一段的开始和最后一段的结束
        first_segment = t.split(",")[0].strip()
        last_segment = t.split(",")[-1].strip()
        # 解析开始时间
        open_part = first_segment.split("-")[0].strip()
        # 解析结束时间
        close_part = last_segment.split("-")[-1].strip()

        def parse_time(s):
            s = s.replace("：", ":").strip()
            if ":" in s:
                h, m = s.split(":")[:2]
                return int(h) * 60 + int(m)
            else:
                return int(s[:2]) * 60

        return (parse_time(open_part), parse_time(close_part))
    except Exception:
        return (0, 1440)


def plan_routes(candidate_pois: list, intent: dict, profile: dict, weather: dict,
                start_lat: float = None, start_lng: float = None, city: str = "") -> dict:
    """生成 A/B/C 三套差异化路线方案"""

    if len(candidate_pois) < 3:
        return _empty_plan()

    # 使用用户真实 GPS；若无则以 POI 中心点作为起点
    if start_lat is not None and start_lng is not None and start_lat != 0 and start_lng != 0:
        pass  # 用户真实位置
    else:
        # 用候选 POI 的质心作为默认起点
        lats = [p.get("lat", 0) for p in candidate_pois if p.get("lat")]
        lngs = [p.get("lng", 0) for p in candidate_pois if p.get("lng")]
        if lats and lngs:
            start_lat, start_lng = sum(lats) / len(lats), sum(lngs) / len(lngs)
        else:
            return _empty_plan()

    user_prefs = profile.get("vibe_preferences", []) + intent.get("explicit_preferences", [])
    user_vibe = intent.get("vibe", "休闲")
    budget = intent.get("budget", 500)
    duration_min = int(intent.get("duration_hours", 4) * 60)
    start_time = 14 * 60  # 默认 14:00 开始

    # 评分：综合 vibe 匹配 + 评分 + 价格合理
    def score_poi(poi):
        vibe_score = match_poi_to_user_vibe(poi, user_prefs, user_vibe)
        rating = poi.get("rating", 4.0) / 5.0
        price = poi.get("avg_price", 100)
        price_score = 1 - abs(price - budget * 0.15) / max(budget * 0.15, 1)
        return vibe_score * 0.45 + rating * 0.35 + max(0, price_score) * 0.2

    scored = sorted([(score_poi(p), p) for p in candidate_pois], key=lambda x: -x[0])

    # 方案 A: 最优体验 (vibe 优先)
    plan_a = _greedy_route(scored[:30], start_lat, start_lng, start_time, duration_min, budget, "vibe")

    # 方案 B: 性价比 (预算优先)
    cheap_scored = sorted(
        [(p.get("avg_price", 100), p) for _, p in scored[:30]],
        key=lambda x: x[0]
    )
    plan_b = _greedy_route(
        [(1 - p[0] / max(budget, 1), p[1]) for p in cheap_scored[:30]],
        start_lat, start_lng, start_time, duration_min, budget * 0.7, "budget"
    )

    # 方案 C: 高效紧凑 (时间优先)
    plan_c = _greedy_route(
        scored[:15], start_lat, start_lng, start_time, int(duration_min * 0.65), budget, "time"
    )

    return {
        "plan_a": plan_a,
        "plan_b": plan_b,
        "plan_c": plan_c,
        "weather_advice": weather.get("constraints", {}).get("advice", ""),
    }


def _greedy_route(scored_pois, start_lat, start_lng, start_time, max_duration, budget, strategy):
    """贪心构造路线"""
    route = []
    total_cost = 0
    total_time = 0
    current_lat, current_lng = start_lat, start_lng
    current_time = start_time

    for score, poi in scored_pois:
        if len(route) >= 5:
            break

        price = poi.get("avg_price", 100)
        if total_cost + price > budget:
            continue

        dist = haversine(current_lat, current_lng, poi.get("lat", current_lat), poi.get("lng", current_lng))
        # 步行速度约 5km/h，骑行约 15km/h，驾车约 30km/h
        walk_speed = 5.0
        bike_speed = 15.0
        speed = walk_speed if strategy != "time" else bike_speed
        travel_time = int(dist / speed * 60)

        stay_time = _estimate_stay(poi, strategy)
        arrival = current_time + travel_time

        # 营业时间检查
        open_min, close_min = time_to_minutes(poi.get("open_time", ""))
        if arrival + stay_time > close_min:
            continue

        if current_time + travel_time + stay_time > start_time + max_duration:
            continue

        total_time += travel_time + stay_time
        total_cost += price

        route.append({
            "poi_id": poi.get("poi_id", ""),
            "name": poi["name"],
            "category": poi.get("category", ""),
            "arrival_time": f"{arrival // 60:02d}:{arrival % 60:02d}",
            "stay_minutes": stay_time,
            "travel_from_prev": f"步行{travel_time}分钟" if travel_time < 20 else f"骑行{travel_time}分钟" if travel_time < 60 else f"驾车{travel_time}分钟",
            "cost": price,
            "rating": poi.get("rating", 4.0),
            "tags": poi.get("tags", []),
            "ugc_summary": poi.get("ugc_summary", ""),
            "lat": poi.get("lat", current_lat),
            "lng": poi.get("lng", current_lng),
            "weather_sensitive": poi.get("weather_sensitive", "both"),
        })
        current_lat = poi.get("lat", current_lat)
        current_lng = poi.get("lng", current_lng)
        current_time = arrival + stay_time

    return {
        "strategy": strategy,
        "label": {"vibe": "体验优先", "budget": "性价比之选", "time": "高效紧凑"}[strategy],
        "stops": route,
        "total_cost": total_cost,
        "total_time_minutes": total_time,
        "poi_count": len(route),
    }


def _estimate_stay(poi, strategy) -> int:
    cat = poi.get("category", "")
    base = {"餐饮": 60, "景点": 90, "购物": 40, "休闲": 45}.get(cat, 60)
    if strategy == "time":
        base = int(base * 0.7)
    return base


async def generate_description(plan: dict, intent: dict, weather: dict) -> str:
    """用 LLM 将方案转为自然语言描述"""
    weather_advice = weather.get("constraints", {}).get("advice", "")
    stops_text = "\n".join(
        f"{s['arrival_time']} {s['name']} | {s['category']} | 人均{s['cost']}元 | {s['travel_from_prev']} | {', '.join(s.get('tags', []))}"
        for s in plan.get("stops", [])
    )
    user_msg = f"""
天气建议: {weather_advice}
路线方案({plan.get('label','')}): 共{plan.get('total_cost',0)}元, {plan.get('total_time_minutes',0)}分钟

{stops_text}

请生成路线描述。"""

    try:
        desc = await llm_service.chat(ROUTE_DESCRIPTION_PROMPT, user_msg, temperature=0.8, max_tokens=512)
        return desc
    except Exception:
        return _fallback_description(plan, weather_advice)


def _fallback_description(plan: dict, weather_advice: str) -> str:
    lines = [weather_advice, ""]
    for i, s in enumerate(plan.get("stops", []), 1):
        tags = "、".join(s.get("tags", [])[:3])
        lines.append(f"{s['arrival_time']} {s['name']}，{s['category']}，人均{s['cost']}元，{tags}")
        if i < len(plan.get("stops", [])):
            lines.append(f"  ↳ {s.get('travel_from_prev', '步行')}到下一站")
    lines.append(f"\n全程约{plan.get('total_time_minutes', 0)}分钟，总预算约{plan.get('total_cost', 0)}元。")
    return "\n".join(lines)


def _empty_plan():
    return {
        "plan_a": {"strategy": "vibe", "label": "体验优先", "stops": [], "total_cost": 0, "total_time_minutes": 0, "poi_count": 0},
        "plan_b": {"strategy": "budget", "label": "性价比之选", "stops": [], "total_cost": 0, "total_time_minutes": 0, "poi_count": 0},
        "plan_c": {"strategy": "time", "label": "高效紧凑", "stops": [], "total_cost": 0, "total_time_minutes": 0, "poi_count": 0},
        "weather_advice": "暂无天气数据",
    }
