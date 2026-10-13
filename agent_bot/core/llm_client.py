"""LLM client: Gemini (REST) + Mock fallback.

Design goals for a strong agent:
- Single async interface, easy to swap models (Gemini today, Claude/GPT tomorrow).
- No crash without API key: factory returns Mock client so bot/handlers/tests work offline.
- Plain-text Markdown contract: model must return plain-text Markdown only (HTML forbidden),
  telegram/formatting converts it to safe HTML on send.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from agent_bot.config.settings import settings

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)


@dataclass
class LLMResponse:
    text: str
    model: str


class BaseLLMClient:
    async def generate(self, system_instruction: str, prompt: str) -> LLMResponse:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    """Offline/test client. Returns deterministic plain-text Markdown."""

    async def generate(self, system_instruction: str, prompt: str) -> LLMResponse:
        _ = system_instruction  # contract: system role already built by MetaPromptEngine
        return LLMResponse(
            text=(
                "## Asosiy Xulosa\n"
                "**[ESTIMATED]** Mock rejim: API kalit topilmadi, lekin orkestr ishlayapti.\n\n"
                "## Texnik tahlil\n"
                "- So'rov qabul qilindi va `prompt` qurildi.\n"
                "- Real javob uchun `.env` ga `GEMINI_API_KEY` qo'ying.\n\n"
                "> Keyingi qadam: kalit qo'yib qayta so'rang."
            ),
            model="mock-1",
        )


class GeminiClient(BaseLLMClient):
    """Gemini REST client via aiohttp (no heavy SDK dependency at runtime)."""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        self.api_key = api_key
        self.model = model or settings.gemini_model
        self.timeout = aiohttp.ClientTimeout(total=timeout or settings.llm_timeout_s)
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens
        self._endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )

    async def generate(self, system_instruction: str, prompt: str) -> LLMResponse:
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": self.temperature, "maxOutputTokens": self.max_tokens},
        }
        params = {"key": self.api_key}
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as sess:
                    async with sess.post(self._endpoint, params=params, json=payload) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            logger.error("Gemini HTTP %s: %s", resp.status, body[:500])
                            # 4xx (kalit/reja xatosi) da retry foydasiz
                            if 400 <= resp.status < 500:
                                raise RuntimeError(f"Gemini HTTP {resp.status}")
                            last_err = RuntimeError(f"Gemini HTTP {resp.status}")
                            continue
                        data = await resp.json()
                break
            except RuntimeError:
                raise
            except Exception as exc:  # network/timeout -> retry
                last_err = exc
                logger.warning("Gemini attempt %d failed: %s", attempt + 1, exc)
                await asyncio.sleep(1.0 * (attempt + 1))
        else:
            raise RuntimeError(f"Gemini request failed after retries: {last_err}")

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Gemini bad response: %s", str(data)[:500])
            raise RuntimeError("Gemini bad response shape") from exc

        if not text:
            raise RuntimeError("Gemini empty response")
        return LLMResponse(text=text, model=self.model)


def get_llm_client(api_key: Optional[str] = None) -> BaseLLMClient:
    """Factory: real Gemini if key present, else Mock (never crashes)."""
    key = api_key or settings.gemini_api_key
    if key:
        return GeminiClient(api_key=key)
    logger.warning("GEMINI_API_KEY missing -> MockLLMClient")
    return MockLLMClient()
