"""Enhanced Multi-Model Router supporting Gemini 3.8 Flash, Groq, OpenRouter, OpenAI, and Local GPU."""
import os
import logging
import aiohttp
from typing import Dict, Any, Optional
from pydantic import BaseModel
from agent_bot.config.settings import Settings

logger = logging.getLogger(__name__)

async def _call_compat(client, system_instruction: str, prompt: str) -> tuple[str, str]:
    """OpenAICompatClient (LLMResponse: .text/.model) -> (text, model)."""
    resp = await client.generate(system_instruction, prompt)
    return resp.text.strip(), resp.model

class ModelResponse(BaseModel):
    content: str
    provider: str
    model_name: str
    success: bool = True
    error_message: Optional[str] = None

class ModelRouter:
    """Universal ko'p modelli aqlli router (Avtomatik Fallback kaskadi).

    Ustuvorlik tartibi:
    0. Anthropic Claude (asosiy miya — uzun ufqli agent ishlar), kalit bo'lsa;
    1. Google Gemini (gemini-3.8-flash);
    2. Groq Cloud (qwen/qwen3.8-27b) - Chaqmoqdek tez (<1 soniya);
    3. OpenRouter (liquid/lfm-2.5-2.6b:free) - Bepul zaxira;
    4. OpenAI (gpt-4o-mini);
    5. Mahalliy RTX 4050 / Ollama (oflayn);
    6. Offline Safe Rules Engine.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._gemini_client = None

        if settings.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
            except Exception as e:
                logger.warning(f"Gemini client xatosi: {e}")

    async def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        model_preference: Optional[str] = None
    ) -> ModelResponse:
        # 1. Agar maxsus Gemini so'ralgan bo'lsa
        if model_preference and "gemini" in model_preference.lower() and self._gemini_client:
            for g_model in ["gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"]:
                try:
                    config = {}
                    if system_instruction:
                        config["system_instruction"] = system_instruction
                    response = self._gemini_client.models.generate_content(
                        model=g_model,
                        contents=prompt,
                        config=config
                    )
                    return ModelResponse(
                        content=response.text.strip(),
                        provider="Google Gemini (2026)",
                        model_name=g_model
                    )
                except Exception as e:
                    logger.warning(f"Gemini {g_model} API xatoligi: {e}")

        # 0. Anthropic Claude (asosiy miya — barcha murakkab ishni boshqaradi)
        if self.settings.anthropic_api_key:
            try:
                from agent_bot.core.anthropic_client import AnthropicClient

                client = AnthropicClient(
                    api_key=self.settings.anthropic_api_key,
                    model=model_preference or self.settings.anthropic_model,
                )
                text, used_model = await _call_compat(
                    client, system_instruction, prompt
                )
                return ModelResponse(
                    content=text,
                    provider="Anthropic Claude",
                    model_name=used_model,
                )
            except Exception as e:
                logger.error(f"Claude API xatoligi: {e}. Keyingi provayderga o'tilmoqda...")

        # 2. Groq Cloud (openai/gpt-oss-120b GPT-6 Reasoning yoki qwen/qwen3.8-27b Fast)
        if self.settings.groq_api_key:
            try:
                res = await self._call_groq(prompt, system_instruction, model_preference)
                if res.success:
                    return res
            except Exception as e:
                logger.error(f"Groq API xatoligi: {e}. Gemini provayderiga o'tilmoqda...")

        # 3. Google Gemini (2026-yilgi eng yangi rasmiy modellar)
        if self._gemini_client:
            for g_model in ["gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"]:
                try:
                    config = {}
                    if system_instruction:
                        config["system_instruction"] = system_instruction

                    response = self._gemini_client.models.generate_content(
                        model=g_model,
                        contents=prompt,
                        config=config
                    )
                    return ModelResponse(
                        content=response.text.strip(),
                        provider="Google Gemini (2026)",
                        model_name=g_model
                    )
                except Exception as e:
                    logger.warning(f"Gemini {g_model} API xatoligi: {e}")


        # 3. OpenRouter (Zaxira bepul provayder)
        if self.settings.openrouter_api_key:
            try:
                res = await self._call_openrouter(prompt, system_instruction, model_preference)
                if res.success:
                    return res
            except Exception as e:
                logger.error(f"OpenRouter API xatoligi: {e}. OpenAI provayderiga o'tilmoqda...")

        # 4. OpenAI (yagona aiohttp mijoz orqali — openai SDK paketi kerak emas)
        if self.settings.openai_api_key:
            try:
                from agent_bot.core.openai_client import OpenAICompatClient

                client = OpenAICompatClient(
                    api_key=self.settings.openai_api_key,
                    model=model_preference or self.settings.openai_model,
                    base_url=self.settings.openai_base_url,
                )
                text, used_model = await _call_compat(
                    client, system_instruction, prompt
                )
                return ModelResponse(
                    content=text,
                    provider="OpenAI",
                    model_name=used_model,
                )
            except Exception as e:
                logger.error(f"OpenAI API xatoligi: {e}")

        # 5. Mahalliy Ollama / RTX 4050 (6GB VRAM ga sig'adigan default model)
        local_model = model_preference or self.settings.local_model
        try:
            async with aiohttp.ClientSession() as session:
                ollama_payload = {
                    "model": local_model,
                    "prompt": f"{system_instruction}\n\n{prompt}",
                    "stream": False
                }
                async with session.post(
                    "http://localhost:11434/api/generate",
                    json=ollama_payload,
                    timeout=aiohttp.ClientTimeout(total=8.0)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return ModelResponse(
                            content=data.get("response", "").strip(),
                            provider="Local RTX 4050 (Ollama)",
                            model_name=local_model
                        )
        except Exception:
            pass

        # 6. Offline Fallback
        fallback_content = (
            "⚙️ **[UNIVERSAL AGENT BOT — OFLAYN XABAR]**\n\n"
            "Tizim muvaffaqiyatli qabul qilindi, biroq barcha AI API provayderlar vaqtinchalik javob bermadi.\n\n"
            "📌 **Sizning topshirig'ingiz:**\n"
            f"> {prompt[:200]}..."
        )

        return ModelResponse(
            content=fallback_content,
            provider="Local Rules Engine",
            model_name="offline-rules"
        )

    async def _call_groq(self, prompt: str, system_instruction: str, model: Optional[str]) -> ModelResponse:
        """Groq Cloud API asinxron chaqiruvi (120B GPT-6 Reasoning + Fast Qwen)."""
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        if model == "fast":
            candidate_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]
        elif model in ("gpt6", "deep"):
            candidate_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
        elif model and "/" in model:
            candidate_models = [model, "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
        else:
            # Standart flagman: 120B Reasoning birinchi, zaxirada 27B Fast
            candidate_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        for m_name in candidate_models:
            cur_max_tokens = 900 if "qwen" in m_name else 1800
            payload = {
                "model": m_name,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": cur_max_tokens
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30.0)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            msg = data["choices"][0]["message"]
                            content = (msg.get("content") or "").strip()
                            reasoning = (msg.get("reasoning") or "").strip()
                            if not content and reasoning:
                                content = reasoning
                            if content:
                                prov = "Groq 120B (GPT-6 Reasoning)" if "120b" in m_name else "Groq Fast"
                                return ModelResponse(content=content, provider=prov, model_name=m_name)
                        err_text = await resp.text()
                        logger.warning(f"Groq {m_name} muvaffaqiyatsiz: {err_text}")
            except Exception as e:
                logger.warning(f"Groq {m_name} chaqiruv xatosi: {e}")

        return ModelResponse(content="", provider="Groq", model_name="fallback", success=False)

    async def _call_openrouter(self, prompt: str, system_instruction: str, model: Optional[str]) -> ModelResponse:
        """OpenRouter API asinxron chaqiruvi."""
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/agent-bot",
            "X-Title": "Agent Bot"
        }
        candidate_models = [model] if model else [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "google/gemma-4-26b-a4b-it:free",
            "liquid/lfm-2.5-2.6b:free"
        ]
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        for m_name in candidate_models:
            payload = {
                "model": m_name,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 1500
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=25.0)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = data["choices"][0]["message"]["content"].strip()
                            return ModelResponse(content=content, provider="OpenRouter", model_name=m_name)
                        err_text = await resp.text()
                        logger.warning(f"OpenRouter {m_name} muvaffaqiyatsiz: {err_text}")
            except Exception as e:
                logger.warning(f"OpenRouter {m_name} chaqiruv xatosi: {e}")

        return ModelResponse(content="", provider="OpenRouter", model_name="fallback", success=False)
