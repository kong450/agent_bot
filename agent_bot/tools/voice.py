"""JARVIS voice layer: speech-to-text (Whisper) + text-to-speech (Orpheus) via Groq.

STT: POST /openai/v1/audio/transcriptions (multipart), model whisper-large-v3-turbo,
     99+ til (o'zbek/rus/ingliz), free tier 20 RPM / 2000 kuniga.
TTS: POST /openai/v1/audio/speech, Orpheus — FAQAT ingliz/arabl (o'zbek ovoz yo'q!).
     Cheklovlar: input max 200 belgi (avtomatik bo'lib yuboriladi), javob faqat wav.

Qoida: GROQ_API_KEY bo'lmasa — aniq xato, jim o'lish yo'q.
"""
from __future__ import annotations

import io
import logging
import re
from typing import List, Optional

import aiohttp

from agent_bot.config.settings import settings

logger = logging.getLogger(__name__)

_GROQ_BASE = "https://api.groq.com/openai/v1"
_STT_MODEL = "whisper-large-v3-turbo"
_TTS_MODEL = "canopylabs/orpheus-v1-english"
_TTS_VOICE = "austin"
_TTS_LIMIT = 200  # Orpheus input limiti
_STT_TIMEOUT = aiohttp.ClientTimeout(total=60)
_TTS_TIMEOUT = aiohttp.ClientTimeout(total=60)


def _require_groq_key() -> str:
    key = settings.groq_api_key
    if not key:
        raise RuntimeError("GROQ_API_KEY topilmadi (.env ga qo'shing).")
    return key


def split_for_tts(text: str, limit: int = _TTS_LIMIT) -> List[str]:
    """Matnni 200 belgilik TTS bo'laklariga jumla chegarasida bo'ladi."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    sentences = re.split(r"(?<=[.!?…])\s+", clean)
    chunks: List[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= limit and buf:
            buf = f"{buf} {s}"
            continue
        if buf:
            chunks.append(buf)
        while len(s) > limit:  # bitta uzun jumla -> so'z chegarasida
            cut = s.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            chunks.append(s[:cut])
            s = s[cut:].lstrip()
        buf = s
    if buf:
        chunks.append(buf)
    return chunks


async def transcribe_voice(
    audio: bytes, filename: str = "voice.ogg", language: Optional[str] = None
) -> str:
    """Ovozli xabarni matnga o'giradi. Qaytaradi: matn (bo'sh bo'lmaydi)."""
    if not audio:
        raise ValueError("bo'sh audio")
    key = _require_groq_key()
    form = aiohttp.FormData()
    form.add_field("file", io.BytesIO(audio), filename=filename,
                   content_type="audio/ogg")
    form.add_field("model", _STT_MODEL)
    form.add_field("response_format", "text")
    if language:
        form.add_field("language", language)
    headers = {"Authorization": f"Bearer {key}"}
    async with aiohttp.ClientSession(timeout=_STT_TIMEOUT) as sess:
        async with sess.post(
            f"{_GROQ_BASE}/audio/transcriptions", data=form, headers=headers
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                logger.error("Whisper HTTP %s: %s", resp.status, body[:300])
                raise RuntimeError(f"Whisper HTTP {resp.status}")
            text = body.strip().strip('"')
            if not text:
                raise RuntimeError("Whisper bo'sh javob qaytardi")
            return text


async def synthesize_speech(text: str, voice: str = _TTS_VOICE) -> List[bytes]:
    """Matnni inglizcha ovoz (wav bo'laklari) ga aylantiradi.

    Diqqat: Orpheus o'zbek tilini bilmaydi — inglizcha matn uchun.
    """
    key = _require_groq_key()
    chunks = split_for_tts(text)
    if not chunks:
        raise ValueError("o'qiladigan matn yo'q")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    out: List[bytes] = []
    async with aiohttp.ClientSession(timeout=_TTS_TIMEOUT) as sess:
        for part in chunks[:8]:  # haddan tashqari uzun javobni cheklash
            payload = {"model": _TTS_MODEL, "input": part,
                       "voice": voice, "response_format": "wav"}
            async with sess.post(
                f"{_GROQ_BASE}/audio/speech", json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Orpheus HTTP %s: %s", resp.status, body[:300])
                    raise RuntimeError(f"TTS HTTP {resp.status}")
                out.append(await resp.read())
    return out
