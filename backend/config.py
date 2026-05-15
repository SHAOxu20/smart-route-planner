import os
from dotenv import load_dotenv

load_dotenv()

# LLM 配置 — 支持多平台
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # ollama / claude / deepseek / openai
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")     # ollama 无需真实 key
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")

# 高德地图
AMAP_API_KEY = os.getenv("AMAP_API_KEY", "")

# 和风天气
QWEATHER_API_KEY = os.getenv("QWEATHER_API_KEY", "")

# 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./route_planner.db")
