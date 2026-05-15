"""
天气服务 — 对接和风天气 API，将天气转为路线约束
"""
import httpx
from config import QWEATHER_API_KEY

QWATHER_BASE = "https://devapi.qweather.com/v7"


async def get_weather(city: str = "") -> dict:
    """获取实时天气 + 未来预报，转为系统可用约束"""
    if not city:
        return _mock_weather()
    if not QWEATHER_API_KEY:
        return _mock_weather()

    async with httpx.AsyncClient(timeout=10) as client:
        # 城市查询
        geo_resp = await client.get(
            f"https://geoapi.qweather.com/v2/city/lookup",
            params={"location": city, "key": QWEATHER_API_KEY}
        )
        geo_data = geo_resp.json()
        if geo_data.get("code") != "200" or not geo_data.get("location"):
            return _mock_weather()

        location_id = geo_data["location"][0]["id"]

        # 实时天气 + 24h 预报
        now_resp = await client.get(
            f"{QWATHER_BASE}/weather/now",
            params={"location": location_id, "key": QWEATHER_API_KEY}
        )
        hourly_resp = await client.get(
            f"{QWATHER_BASE}/weather/24h",
            params={"location": location_id, "key": QWEATHER_API_KEY}
        )

        now = now_resp.json().get("now", {})
        hourly = hourly_resp.json().get("hourly", [])

        return _build_weather_result(now, hourly)


def _build_weather_result(now: dict, hourly: list) -> dict:
    text = now.get("text", "晴")
    temp = int(now.get("temp", 25))
    is_rain = any(w in text for w in ["雨", "雪", "雷", "霾"])

    constraints = {
        "is_rain": is_rain,
        "prefer_indoor": is_rain,
        "temperature": temp,
        "advice": "",
    }

    if is_rain:
        constraints["advice"] = f"今日{text}，建议优先选择室内场所，记得带伞。"
    elif temp > 35:
        constraints["advice"] = f"今日高温{temp}°C，建议避开户外暴晒时段。"
        constraints["prefer_indoor"] = True
    elif temp < 5:
        constraints["advice"] = f"今日低温{temp}°C，注意保暖，减少户外停留。"
        constraints["prefer_indoor"] = True
    else:
        constraints["advice"] = f"今日天气{text}，温度{temp}°C，适合出行。"

    return {"weather_text": text, "temperature": temp, "constraints": constraints}


def _mock_weather() -> dict:
    return {
        "weather_text": "多云",
        "temperature": 24,
        "constraints": {
            "is_rain": False,
            "prefer_indoor": False,
            "temperature": 24,
            "advice": "今日多云，温度24°C，适合出行。",
        },
    }
