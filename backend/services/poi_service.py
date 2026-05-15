"""
POI 服务 — 高德地图多维搜索 + 本地预置数据补充
覆盖全品类：景点、餐饮、购物、休闲、文化等
"""
import json
import os
import asyncio
import httpx
from config import AMAP_API_KEY

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# 高德 POI 类型码
AMAP_TYPES = {
    "餐饮": "050000",
    "景点": "110000",
    "购物": "060000",
    "休闲": "080000",
    "咖啡": "050300",
    "茶馆": "050300",
    "公园": "110100",
    "博物馆": "140100",
    "风景": "110000",
}

# 基础搜索维度 — 每个城市都搜这些
BASE_SEARCHES = [
    {"keywords": "热门景点", "types": "110000"},
    {"keywords": "公园", "types": "110100"},
    {"keywords": "博物馆展览馆", "types": "140100"},
    {"keywords": "美食餐厅", "types": "050000"},
    {"keywords": "咖啡厅茶馆", "types": "050300"},
    {"keywords": "商场购物中心", "types": "060100"},
    {"keywords": "夜市步行街", "types": "060000"},
    {"keywords": "休闲娱乐", "types": "080000"},
]


def load_local_pois() -> list:
    path = os.path.join(DATA_DIR, "poi_seed.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_ugc_tags() -> dict:
    path = os.path.join(DATA_DIR, "ugc_tags.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


async def search_pois_amap(keywords: str, city: str = "", poi_types: str = "", offset: int = 20) -> list:
    """单次高德 POI 搜索"""
    if not AMAP_API_KEY or not city:
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        params = {
            "key": AMAP_API_KEY,
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "extensions": "all",
            "offset": offset,
        }
        if poi_types:
            params["types"] = poi_types

        try:
            resp = await client.get("https://restapi.amap.com/v3/place/text", params=params)
            data = resp.json()
        except Exception:
            return []

        if data.get("status") != "1":
            return []

        pois = []
        for p in data.get("pois", []):
            location = p.get("location", "0,0").split(",")
            biz = p.get("biz_ext", {}) or {}
            deep = p.get("deep_info", {}) or {}
            pois.append({
                "poi_id": p.get("id", ""),
                "name": p.get("name", ""),
                "category": _map_category(p.get("type", "")),
                "address": p.get("address", ""),
                "lng": float(location[0]) if len(location) > 0 else 0,
                "lat": float(location[1]) if len(location) > 1 else 0,
                "avg_price": float(biz.get("cost", 0) or deep.get("avg_price", 0) or 0),
                "rating": float(biz.get("rating", "4.0") or "4.0"),
                "open_time": deep.get("opentime", "") or biz.get("opentime", ""),
                "tags": _extract_tags(p),
                "source": "amap",
            })
        return pois


def _map_category(amap_type: str) -> str:
    mapping = [
        (["餐饮", "餐厅", "饭店", "小吃", "火锅", "烧烤", "海鲜", "日料", "面馆", "快餐", "甜品"], "餐饮"),
        (["风景", "公园", "植物园", "动物园", "游乐园", "景区", "名胜"], "景点"),
        (["购物", "商场", "市场", "步行街", "夜市", "超市", "便利店"], "购物"),
        (["咖啡", "茶", "饮料", "冷饮", "甜品"], "休闲"),
        (["博物馆", "展览", "美术馆", "科技馆", "文化宫", "图书馆", "剧院"], "文化"),
        (["体育", "健身", "游泳", "KTV", "酒吧", "网吧", "电影院"], "娱乐"),
        (["住宿", "酒店", "宾馆", "民宿"], "住宿"),
    ]
    for keywords, cat in mapping:
        if any(kw in amap_type for kw in keywords):
            return cat
    return "其他"


def _extract_tags(poi: dict) -> list:
    """从高德 POI 数据中提取标签"""
    tags = []
    t = poi.get("type", "")
    biz = poi.get("biz_ext", {}) or {}

    if "公园" in t: tags.append("公园")
    if "博物馆" in t: tags.append("博物馆")
    if "风景" in t: tags.append("风景名胜")
    if "商场" in t: tags.append("购物中心")
    if "步行街" in t: tags.append("步行街")
    if "夜市" in t: tags.append("夜市")
    if "咖啡" in t: tags.append("咖啡厅")
    if "茶" in t: tags.append("茶馆")

    if biz.get("rating") and float(biz.get("rating", 0)) >= 4.5:
        tags.append("高评分")

    tag_info = poi.get("deep_info", {}).get("tag_info", "")
    if tag_info:
        tags.append(tag_info)

    return tags[:6]


async def get_candidate_pois(intent: dict, weather_constraints: dict) -> list:
    """综合高德多维搜索 + 本地数据生成候选 POI 列表"""
    dest = intent.get("destination", "")
    local_pois = load_local_pois()
    ugc_tags = load_ugc_tags()

    # 并行搜索高德 — 基础维度 + 意图维度
    searches = list(BASE_SEARCHES)

    # 根据用户意图添加定向搜索
    search_kws = intent.get("search_keywords", [])
    for kw in search_kws[:5]:
        searches.append({"keywords": kw, "types": ""})

    # 根据 vibe 添加特定搜索
    vibe_searches = {
        "浪漫": [{"keywords": "西餐厅", "types": "050000"}, {"keywords": "甜品店", "types": "050300"}],
        "高端商务": [{"keywords": "高档餐厅", "types": "050000"}, {"keywords": "私房菜", "types": "050000"}],
        "亲子互动": [{"keywords": "游乐园", "types": "110000"}, {"keywords": "动物园", "types": "110000"}],
        "自然户外": [{"keywords": "风景区", "types": "110000"}, {"keywords": "徒步", "types": "110000"}],
        "热闹活力": [{"keywords": "夜市", "types": "060000"}, {"keywords": "酒吧", "types": "080000"}],
        "文艺格调": [{"keywords": "文创园", "types": "110000"}, {"keywords": "美术馆", "types": "140100"}],
        "安静放松": [{"keywords": "茶馆", "types": "050300"}, {"keywords": "书店", "types": "060000"}],
    }
    vibe = intent.get("vibe", "")
    for s in vibe_searches.get(vibe, []):
        searches.append(s)

    # 去重搜索项
    seen = set()
    unique_searches = []
    for s in searches:
        key = (s["keywords"], s["types"])
        if key not in seen:
            seen.add(key)
            unique_searches.append(s)

    # 并行执行所有搜索
    async def do_search(s):
        return await search_pois_amap(s["keywords"], dest, s["types"], offset=10)

    all_amap = []
    if AMAP_API_KEY and dest:
        results = await asyncio.gather(*[do_search(s) for s in unique_searches])
        for r in results:
            all_amap.extend(r)

    # 合并去重
    all_pois = {}
    for p in local_pois:
        all_pois[p["poi_id"]] = p
    for p in all_amap:
        if p["poi_id"] not in all_pois:
            all_pois[p["poi_id"]] = p

    pois = list(all_pois.values())

    # UGC 标签增强
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

    # 预算剪枝（宽松，留足够候选）
    max_budget = intent.get("budget", 9999)
    if max_budget < 9999:
        pois = [p for p in pois if p.get("avg_price", 0) <= max_budget * 0.8]

    return pois


def _is_indoor(poi: dict) -> bool:
    indoor_cats = {"餐饮", "购物", "休闲", "娱乐", "文化"}
    return poi.get("weather_sensitive", "") == "indoor" or poi.get("category", "") in indoor_cats
