"""
本地智能路线规划系统 — FastAPI 后端
"""
import json
import uuid
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db, UserHistory, POIRecord
from services.intent_parser import parse_intent
from services.weather_service import get_weather
from services.poi_service import get_candidate_pois
from services.ugc_service import match_poi_to_user_vibe, extract_semantic_tags, load_ugc_reviews
from services.user_profile import build_profile, get_user_history
from services.route_planner import plan_routes, generate_description

app = FastAPI(title="LocalSmartRoute", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()


# ─── Request Models ────────────────────────────────

class RouteRequest(BaseModel):
    query: str                          # 自然语言输入
    session_id: str = ""                # 用户会话 ID
    city: str = ""                      # 城市，由前端 GPS 反地理编码获得
    start_lat: float = 0.0              # 用户 GPS 纬度
    start_lng: float = 0.0              # 用户 GPS 经度
    selected_plan: str = ""             # 用户选择的方案 A/B/C


class AdjustRequest(BaseModel):
    session_id: str
    feedback: str                       # "太贵了" / "加个甜品店" / "时间来不及"
    current_plan: dict = {}


# ─── 核心 API ─────────────────────────────────────

@app.post("/api/route/describe")
async def describe_plan(req: dict):
    """懒加载：按需生成单个方案的 LLM 描述"""
    plan = req.get("plan", {})
    intent = req.get("intent", {})
    weather = req.get("weather", {})
    if not plan.get("stops"):
        return {"description": ""}
    desc = await generate_description(plan, intent, weather)
    return {"description": desc}


@app.post("/api/route/plan")
async def plan_route(req: RouteRequest, db: Session = Depends(get_db)):
    """主端点：输入自然语言 → 输出路线方案"""
    sid = req.session_id or str(uuid.uuid4())

    # 1. 读取用户历史
    history = get_user_history(sid, db)

    # 2. 意图解析（规则引擎毫秒级，LLM 可选）
    from services.intent_parser import _fallback_parse
    intent = _fallback_parse(req.query)
    # LLM 解析作为异步后台补充（可选开启）
    # intent = await parse_intent(req.query, history)

    # 3. 天气数据
    weather = await get_weather(req.city)

    # 若用户关注天气，覆盖意图中的天气偏好
    if intent.get("weather_concern"):
        intent["implicit_preferences"] = intent.get("implicit_preferences", []) + ["室内优先"]

    # 4. 用户画像
    profile = await build_profile(intent, history)

    # 5. 候选 POI + 天气约束
    pois = await get_candidate_pois(intent, weather.get("constraints", {}))

    # 6. 路线规划 (传入用户 GPS 坐标，0 表示未获取到)
    user_lat = req.start_lat if req.start_lat != 0 else None
    user_lng = req.start_lng if req.start_lng != 0 else None
    plans = plan_routes(pois, intent, profile, weather, user_lat, user_lng, req.city)

    # 7. 路线描述 — 全部用模板（毫秒级），LLM 润色按需调用 /api/route/describe
    from services.route_planner import _fallback_description
    for key in ["plan_a", "plan_b", "plan_c"]:
        p = plans.get(key, {})
        if p.get("stops"):
            plans[key]["description"] = _fallback_description(p, weather.get("constraints", {}).get("advice", ""))

    # 8. 保存历史
    record = UserHistory(
        session_id=sid,
        query_text=req.query,
        parsed_intent=intent,
        generated_route=plans,
    )
    db.add(record)
    db.commit()

    return {
        "session_id": sid,
        "intent": intent,
        "profile": profile,
        "weather": weather,
        "plans": plans,
    }


@app.post("/api/route/adjust")
async def adjust_route(req: AdjustRequest, db: Session = Depends(get_db)):
    """动态调整：用户反馈 → 方案重规划"""
    history = get_user_history(req.session_id, db)
    if not history:
        raise HTTPException(404, "Session not found")

    last_record = history[0]
    intent = last_record.get("parsed_intent", {})
    if isinstance(intent, str):
        intent = json.loads(intent)

    # 解析反馈
    feedback = req.feedback
    if "贵" in feedback or "便宜" in feedback:
        intent["budget"] = int(intent.get("budget", 500) * 0.6)
    elif "甜品" in feedback or "咖啡" in feedback or "加" in feedback:
        intent["explicit_preferences"] = intent.get("explicit_preferences", []) + ["甜品"]
    elif "时间" in feedback or "来不及" in feedback:
        intent["duration_hours"] = max(1, intent.get("duration_hours", 4) * 0.6)

    weather = await get_weather()
    from services.user_profile import _default_profile
    profile = _default_profile(intent)
    pois = await get_candidate_pois(intent, weather.get("constraints", {}))
    plans = plan_routes(pois, intent, profile, weather, None, None)

    # 模板描述（毫秒级），AI 润色按需
    from services.route_planner import _fallback_description
    advice = weather.get("constraints", {}).get("advice", "")
    for key in ["plan_a", "plan_b", "plan_c"]:
        if plans.get(key, {}).get("stops"):
            plans[key]["description"] = _fallback_description(plans[key], advice)

    record = UserHistory(
        session_id=req.session_id,
        query_text=f"[调整] {feedback}",
        parsed_intent=intent,
        generated_route=plans,
        feedback=feedback,
    )
    db.add(record)
    db.commit()

    return {"session_id": req.session_id, "feedback": feedback, "plans": plans, "weather": weather}


@app.get("/api/weather")
async def weather_endpoint(city: str = ""):
    if not city:
        return {"weather_text": "未知", "temperature": 25, "constraints": {"advice": "请先定位获取城市"}}
    return await get_weather(city)


@app.get("/api/history/{session_id}")
async def user_history(session_id: str, db: Session = Depends(get_db)):
    records = db.query(UserHistory).filter(
        UserHistory.session_id == session_id
    ).order_by(UserHistory.created_at.desc()).limit(20).all()

    return [
        {
            "id": r.id,
            "query_text": r.query_text,
            "parsed_intent": r.parsed_intent,
            "selected_plan": r.selected_plan,
            "feedback": r.feedback,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@app.get("/api/pois")
async def search_pois(keyword: str = "", category: str = "", city: str = ""):
    """POI 搜索 — 聚合本地数据 + 高德"""
    from services.poi_service import load_local_pois, search_pois_amap

    local = load_local_pois()
    # 本地过滤
    if keyword:
        local = [p for p in local if keyword in p.get("name", "") or keyword in p.get("category", "")]
    if category:
        local = [p for p in local if p.get("category") == category]

    # 尝试高德搜索
    amap_pois = await search_pois_amap(keyword, city, category)

    return {"local": local, "amap": amap_pois, "total": len(local) + len(amap_pois)}


@app.get("/api/scenarios")
async def get_scenarios():
    """返回支持的场景模型"""
    import os
    path = os.path.join(os.path.dirname(__file__), "data", "scenarios.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ─── 静态文件 (生产环境) ──────────────────────────

import os as _os
static_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "frontend", "dist")
if _os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    import os as _os

    port = int(os.environ.get("PORT", 8000))
    is_production = os.environ.get("RENDER", False)

    ssl_kwargs = {}
    if not is_production:
        ssl_dir = _os.path.dirname(__file__)
        cert = _os.path.join(ssl_dir, "cert.pem")
        key = _os.path.join(ssl_dir, "key.pem")
        if _os.path.exists(cert) and _os.path.exists(key):
            ssl_kwargs = {"ssl_certfile": cert, "ssl_keyfile": key}

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=not is_production, **ssl_kwargs)
