"""Anthropic Claude client (Messages API, aiohttp — qo'shimcha SDK shart emas).

Endpoint: POST https://api.anthropic.com/v1/messages
Headerlar: x-api-key, anthropic-version: 2023-06-01
Model ID ni console.anthropic.com/docs/models dan tasdiqlang
(masalan: claude-opus-5-5 — noto'g'ri ID da 404 qaytadi, router keyingi halqaga o'tadi).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from agent_bot.config.settings import settings
from agent_bot.core.llm_client import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


def build_headers(api_key: str) -> Dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


def parse_content(data: Dict[str, Any]) -> str:
    """Anthropic javobidan matnni ajratadi. Xato formatda ValueError."""
    blocks: List[Dict[str, Any]] = data.get("content", [])
    texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(texts).strip()
    if not text:
        raise ValueError("Anthropic bo'sh javob")
    return text


class AnthropicClient(BaseLLMClient):
    """Claude — uzun ufqli agent ishlar uchun asosiy miya."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY topilmadi (.env ga qo'shing).")
        self.model = model or settings.anthropic_model
        self.timeout = aiohttp.ClientTimeout(total=timeout or settings.llm_timeout_s)
        self.max_tokens = max_tokens or settings.llm_max_tokens

    async def generate(self, system_instruction: str, prompt: str) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            payload["system"] = system_instruction
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as sess:
                async with sess.post(
                    _ANTHROPIC_URL, headers=build_headers(self.api_key), json=payload
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        err = str(data.get("error", data))[:300]
                        logger.error("Anthropic HTTP %s: %s", resp.status, err)
                        raise RuntimeError(f"Anthropic HTTP {resp.status}: {err}")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Anthropic so'rov xatosi: {exc}") from exc
        return LLMResponse(text=parse_content(data), model=self.model)
