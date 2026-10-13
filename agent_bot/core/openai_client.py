"""OpenAI-compatible chat client (OpenAI / OpenRouter / Ollama-style endpointlar).

Bitta REST implementatsiya — turli provayderlar faqat base_url + model + key bilan farqlanadi.
Gemini ishlamasa ModelRouter shu clientga fallback qiladi.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

import aiohttp

from agent_bot.config.settings import settings
from agent_bot.core.llm_client import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatClient(BaseLLMClient):
    """POST {base_url}/chat/completions — OpenAI format.

    Yagona HTTP mijoz: Groq / OpenRouter / OpenAI / Cerebras / Pollinations /
    Ollama-chat — barchasi faqat base_url + model + key (+ixtiyoriy header) bilan farqlanadi.
    """

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.api_key = api_key
        self.model = model or settings.openai_model
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout or settings.llm_timeout_s)
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens
        self.extra_headers = extra_headers or {}

    async def generate(self, system_instruction: str, prompt: str) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", **self.extra_headers}
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as sess:
                    async with sess.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            logger.error("OpenAI-compat HTTP %s: %s", resp.status, body[:500])
                            if 400 <= resp.status < 500:
                                raise RuntimeError(f"OpenAI-compat HTTP {resp.status}")
                            last_err = RuntimeError(f"OpenAI-compat HTTP {resp.status}")
                            continue
                        data = await resp.json()
                break
            except RuntimeError:
                raise
            except Exception as exc:
                last_err = exc
                logger.warning("OpenAI-compat attempt %d failed: %s", attempt + 1, exc)
                await asyncio.sleep(1.0 * (attempt + 1))
        else:
            raise RuntimeError(f"OpenAI-compat failed after retries: {last_err}")

        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenAI-compat bad response shape") from exc
        if not text:
            raise RuntimeError("OpenAI-compat empty response")
        return LLMResponse(text=text, model=self.model)
