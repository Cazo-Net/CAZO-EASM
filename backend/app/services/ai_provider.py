from app.config import settings
from typing import Optional, Dict, Any, List
import httpx
import json
import logging
import time

logger = logging.getLogger(__name__)


class AIProvider:
    """Abstract LLM provider interface."""

    def __init__(self, api_key: str, base_url: str, model: str, temperature: float = 0.7, max_tokens: int = 2048):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """OpenAI-compatible provider."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.base_url:
            self.base_url = "https://api.openai.com/v1"

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                },
            )
            response.raise_for_status()
            data = response.json()
            elapsed_ms = int((time.time() - start) * 1000)
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model", self.model),
                "tokens": data.get("usage", {}).get("total_tokens", 0),
                "response_time_ms": elapsed_ms,
            }


class OllamaProvider(AIProvider):
    """Local Ollama provider."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.base_url:
            self.base_url = "http://localhost:11434"

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        start = time.time()
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", self.temperature),
                        "num_predict": kwargs.get("max_tokens", self.max_tokens),
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            elapsed_ms = int((time.time() - start) * 1000)
            return {
                "content": data["message"]["content"],
                "model": data.get("model", self.model),
                "tokens": 0,
                "response_time_ms": elapsed_ms,
            }


class StubProvider(AIProvider):
    """Stub provider for when no API key is configured."""

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        user_msg = messages[-1]["content"] if messages else ""
        return {
            "content": self._generate_response(user_msg),
            "model": "stub",
            "tokens": 0,
            "response_time_ms": 50,
        }

    def _generate_response(self, query: str) -> str:
        q = query.lower()
        if "summary" in q or "summarize" in q:
            return json.dumps({
                "summary": "Based on your platform data, here is an overview of your current attack surface.",
                "key_observations": [
                    "Your platform contains active scan data across multiple projects.",
                    "There are assets and findings that may require attention.",
                    "Recent activity shows ongoing monitoring and analysis."
                ],
                "recommendations": [
                    "Review any pending recommendations in the dashboard.",
                    "Check certificate expiration dates for upcoming renewals.",
                    "Consider running a new scan to update your asset inventory."
                ]
            }, indent=2)
        if "certificate" in q or "ssl" in q:
            return json.dumps({
                "summary": "Certificate analysis based on your current scan data.",
                "key_observations": [
                    "SSL certificates are tracked across your discovered subdomains.",
                    "Expiration dates are monitored for upcoming renewals.",
                    "Certificate grades reflect the security configuration."
                ],
                "recommendations": [
                    "Monitor certificates expiring within 30 days.",
                    "Review certificates with grades below A.",
                    "Set up automated alerts for certificate changes."
                ]
            }, indent=2)
        if "recommend" in q:
            return json.dumps({
                "summary": "Here are recommendations based on your platform data.",
                "recommendations": [
                    {"title": "Review certificate expirations", "priority": "high", "description": "Check for certificates expiring soon."},
                    {"title": "Update asset inventory", "priority": "medium", "description": "Run a scan to discover new assets."},
                    {"title": "Review findings", "priority": "medium", "description": "Address high-severity findings."}
                ]
            }, indent=2)
        return json.dumps({
            "summary": f"Here is my analysis based on your query: {query[:100]}",
            "key_observations": [
                "The query has been processed through the context engine.",
                "Results are based on your authorized platform data.",
                "No sensitive data was exposed outside your permissions."
            ],
            "suggestions": [
                "Ask me about specific assets or projects.",
                "Request a detailed report on any topic.",
                "Search for specific technologies or certificates."
            ]
        }, indent=2)


def get_ai_provider(settings_obj=None) -> AIProvider:
    """Factory function to get the configured AI provider."""
    s = settings_obj or settings
    api_key = getattr(s, "AI_API_KEY", "")
    base_url = getattr(s, "AI_BASE_URL", "")
    model = getattr(s, "AI_MODEL", "gpt-4o-mini")
    temperature = getattr(s, "AI_TEMPERATURE", 0.7)
    max_tokens = getattr(s, "AI_MAX_TOKENS", 2048)

    if api_key:
        if "ollama" in base_url.lower() or "localhost" in base_url.lower():
            return OllamaProvider(api_key=api_key, base_url=base_url, model=model, temperature=temperature, max_tokens=max_tokens)
        return OpenAIProvider(api_key=api_key, base_url=base_url, model=model, temperature=temperature, max_tokens=max_tokens)

    return StubProvider(api_key="", base_url="", model="stub")
