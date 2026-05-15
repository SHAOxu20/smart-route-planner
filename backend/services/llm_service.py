"""
多平台 LLM 服务 — 支持 Ollama / Claude / DeepSeek / OpenAI
默认使用本地 Ollama (qwen2.5:7b)，无需 API Key
"""
import json
import httpx
from config import LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

ROUTE_PLANNER_SYSTEM = """你是路线规划AI。意图解析时仅输出JSON。约会→氛围感+拍照，亲子→互动+安全，商务→高档+包间，下雨→室内优先，便宜→经济档。"""


class LLMService:
    def __init__(self):
        self.provider = LLM_PROVIDER
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL
        self.model = LLM_MODEL

    async def chat(self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        """统一聊天接口"""
        full_system = ROUTE_PLANNER_SYSTEM + "\n" + system_prompt

        if self.provider == "claude":
            return await self._claude_chat(full_system, user_message, temperature, max_tokens)
        elif self.provider == "ollama":
            return await self._ollama_chat(full_system, user_message, temperature, max_tokens)
        elif self.provider == "deepseek":
            return await self._openai_compat_chat(full_system, user_message, temperature, max_tokens)
        else:
            return await self._openai_compat_chat(full_system, user_message, temperature, max_tokens)

    async def _ollama_chat(self, system: str, user: str, temp: float, max_tokens: int) -> str:
        """Ollama 原生 API"""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "system": system,
                    "prompt": user,
                    "stream": False,
                    "options": {
                        "temperature": temp,
                        "num_predict": max_tokens,
                    },
                },
            )
            data = resp.json()
            return data.get("response", "")

    async def _openai_compat_chat(self, system: str, user: str, temp: float, max_tokens: int) -> str:
        """OpenAI 兼容 API (DeepSeek / Ollama v1 / OpenAI)"""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": temp,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _claude_chat(self, system: str, user: str, temp: float, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": temp,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            data = resp.json()
            return data["content"][0]["text"]


llm_service = LLMService()
