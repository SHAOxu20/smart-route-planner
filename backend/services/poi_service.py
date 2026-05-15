"""
POI 服务 — 多平台数据聚合 (高德地图 + 本地预置数据)
"""
import json
import os
import httpx
from typing import Optional
from config import AMAP_API_KEY

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_local_pois() -> list:
    """加载本地预置 POI 数据"""
    path = os.path.join(DATA_DIR, "poi_seed.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_ugc_tags() -> dict:
    """加载 UGC 标签数据"""
    path = os.path.join(DATA_DIR, "ugc_tags.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


async def search_pois_amap(keywords: str, city: str = "", poi_type: str = "") -> list:
    """高德 POI 搜索"""
    if not AMAP_API_KEY:
        return []

    types_map = {
        "餐饮": "050000", "景点": "110000", "购物": "060000",
        "休闲": "080000", "咖啡": "050300", "甜品": "050300",
    }
    amap_type = types_map.get(poi_type, "")

    async with httpx.AsyncClient(timeout=10) as client:
        params = {
            "key": AMAP_API_KEY,
            "keywords": keywords or poi_type,
            "city": city,
            "citylimit": "true",
            "extensions": "all",
            "offset": 20,
        }
        if amap_type:
            params["types"] = amap_type

        resp = await client.get("https://restapi.amap.com/v3/place/text", params=params)
        data = resp.json()

        if data.get("status") != "1":
            return []

        pois = []
        for p in data.get("pois", []):
            location = p.get("location", "0,0").split(",")
            pois.append({
                "poi_id": p.get("id", ""),
                "name": p.get("name", ""),
                "category": _map_category(p.get("type", "")),
                "address": p.get("address", ""),
                "lng": float(location[0]) if len(location) > 0 else 0,
                "lat": float(location[1]) if len(location) > 1 else 0,
                "avg_price": 0,
                "rating": float(p.get("biz_ext", {}).get("rating", 4.0) or 4.0),
                "open_time": "",
                "tags": [],
                "source": "amap",
            })
        return pois


def _map_category(amap_type: str) -> str:
    if "餐饮" in amap_type: return "餐饮"
    if "风景" in amap_type or "公园" in amap_type: return "景点"
    if "购物" in amap_type: return "购物"
    if "咖啡" in amap_type or "茶" in amap_type: return "休闲"
    return "其他"


async def get_candidate_pois(intent: dict, weather_constraints: dict) -> list:
    """综合本地数据 + 高德 API 生成候选 POI 列表"""
    local_pois = load_local_pois()
    ugc_tags = load_ugc_tags()

    # 也尝试搜索高德
    amap_pois = []
    dest = intent.get("destination", "")
    purpose = intent.get("purpose", "游玩")

    if AMAP_API_KEY and dest:
        if purpose in ("餐饮", "商务应酬"):
            amap_pois = await search_pois_amap("餐厅", dest, "餐饮")
        else:
            amap_pois = await search_pois_amap("景点", dest, "景点")
            amap_pois += await search_pois_amap("咖啡厅", dest, "咖啡")

    # 合并，去重
    all_pois = {p["poi_id"]: p for p in local_pois}
    for p in amap_pois:
        if p["poi_id"] not in all_pois:
            all_pois[p["poi_id"]] = p

    pois = list(all_pois.values())

    # 用 UGC 标签增强
    for poi in pois:
        tag_info = ugc_tags.get(poi["poi_id"], {})
        if tag_info:
            poi["tags"] = list(set(poi.get("tags", []) + tag_info.get("tags", [])))
            poi["ugc_summary"] = tag_info.get("summary", "")
            poi["rating"] = tag_info.get("rating", poi.get("rating", 4.0))
            poi["avg_price"] = tag_info.get("avg_price", poi.get("avg_price", 0))

    # 天气约束过滤
    if weather_constraints.get("prefer_indoor"):
        pois = [p for p in pois if _is_indoor(p)]

    # 预算剪枝
    max_budget = intent.get("budget", 9999)
    pois = [p for p in pois if p.get("avg_price", 0) <= max_budget * 0.6]

    return pois


def _is_indoor(poi: dict) -> bool:
    indoor_cats = {"餐饮", "购物", "休闲", "咖啡"}
    return poi.get("weather_sensitive", "") == "indoor" or poi.get("category", "") in indoor_cats
