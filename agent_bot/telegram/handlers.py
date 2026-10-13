"""aiogram v3 handlers: thin Telegram layer over AgentOrchestrator.

Access control, rate-limit, typing, HTML->plain fallback, file sending,
inline actions (file/variant/shorten) va destructive confirm flow.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from agent_bot.agents.orchestrator import AgentOrchestrator
from agent_bot.config.settings import settings
from agent_bot.memory.profile import load_profile, save_profile

logger = logging.getLogger(__name__)
router = Router()

# Runtime'dagi YAGONA orchestrator instance.
# main.py aynan shu obyektni dp["orchestrator"] ga uzatadi — ikki miya yo'q.
orchestrator = AgentOrchestrator()

# Simple process-local rate limit: user_id -> [timestamps] (bounded)
_MAX_TRACKED_USERS = 2000
_hits: Dict[int, List[float]] = defaultdict(list)

# Tasdiq kutilayotgan oqibatli so'rovlar: user_id -> text (bounded)
_pending_confirm: Dict[int, str] = {}


def _get_user_id(message: Message) -> Optional[int]:
    fu = message.from_user
    return fu.id if fu is not None else None


def _rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    if len(_hits) >= _MAX_TRACKED_USERS and user_id not in _hits:
        oldest = next(iter(_hits))
        del _hits[oldest]
    window = _hits[user_id]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= settings.rate_limit_per_minute:
        return True
    window.append(now)
    return False


def _actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Faylga chiqar", callback_data="act:file"),
                InlineKeyboardButton(text="➕ Yana variant", callback_data="act:more"),
                InlineKeyboardButton(text="✂️ Qisqartir", callback_data="act:short"),
            ]
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm:yes"),
                InlineKeyboardButton(text="❌ Bekor", callback_data="confirm:no"),
            ]
        ]
    )


async def _typing_loop(bot, chat_id: int, stop: asyncio.Event) -> None:
    """Uzun LLM kutishda typing indikatorini tirik ushlab turadi."""
    try:
        while not stop.is_set():
            try:
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass


async def _send_result(message: Message, user_id: int, text_override: Optional[str] = None):
    """Orchestrator -> chunklar + fayllar + inline tugmalar. Qaytaradi: AgentResult yoki None."""
    if message.bot is None:
        return None
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(message.bot, message.chat.id, stop_typing))
    try:
        result = await orchestrator.handle(user_id, text_override or message.text or "")
    except Exception:
        logger.exception("Orchestrator crashed")
        await message.answer("Ichki xatolik. Keyinroq urinib ko'ring.")
        return
    finally:
        stop_typing.set()
        typing_task.cancel()

    if result.needs_confirmation:
        if len(_pending_confirm) >= _MAX_TRACKED_USERS:
            _pending_confirm.pop(next(iter(_pending_confirm)))
        _pending_confirm[user_id] = text_override or message.text or ""
        await message.answer(result.chunks[0], parse_mode=ParseMode.HTML,
                             reply_markup=_confirm_keyboard())
        return result

    chunks = result.chunks or [result.html]
    for i, chunk in enumerate(chunks):
        last = i == len(chunks) - 1
        while True:
            try:
                await message.answer(
                    chunk, parse_mode=ParseMode.HTML,
                    reply_markup=_actions_keyboard() if last else None,
                )
                break
            except TelegramRetryAfter as exc:
                logger.warning("Flood control: %ss kutish", exc.retry_after)
                await asyncio.sleep(exc.retry_after)
                continue
            except TelegramBadRequest:
                logger.warning("HTML send failed, plain fallback")
                await message.answer(result.plain_fallback or "Xatolik", parse_mode=None)
                break
        if last:
            break

    for f in result.files:
        try:
            if Path(f).exists():
                await message.answer_document(FSInputFile(f))
        except Exception:
            logger.exception("File send failed: %s", f)

    return result


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = _get_user_id(message)
    if user_id is None or not settings.is_user_allowed(user_id):
        await message.answer("Ruxsat yo'q.")
        return
    await message.answer(
        "Salom! Men <b>Agent Bot</b> — muhandislik, apparatura mosligi va ilmiy tahlil yordamchingiz.\n\n"
        "Savolingizni oddiy tilda yozing. Masalan:\n"
        "• <code>15 kVt dvigatel momenti qancha?</code>\n"
        "• <code>ESP32 ga 12V motor ulasam bo'ladimi?</code>\n"
        "• <code>Menga Word hisobot tayyorla</code>\n\n"
        "Ovozli xabar ham yuborishingiz mumkin 🎧. Tanishish uchun: <code>/ism Ismingiz</code>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Format: **qalin**, *og'ma*, `kod`, ```blok```, [link](https://...) — barchasi avtomatik chiroyli chiqadi.\n"
        "Jadval va formulalar ham buzilmaydi.\n"
        "Murakkab savolda 2 mutaxassis parallel ishlaydi + QA tekshiradi.\n"
        "Oqibatli amal (o'chirish/to'lov) da avval tasdiq so'rayman.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    user_id = _get_user_id(message)
    if user_id is None:
        return
    orchestrator.store.clear(user_id)
    _pending_confirm.pop(user_id, None)
    await message.answer("Xotira tozalandi.")


@router.message(Command("ism"))
async def cmd_name(message: Message) -> None:
    """JARVIS sizni ismingiz bilan taniydi: /ism Alisher"""
    user_id = _get_user_id(message)
    if user_id is None or not message.text:
        return
    parts = message.text.split(maxsplit=1)
    profile = load_profile(user_id)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            f"Hozirgi ism: <b>{profile.name or '—'}</b>\nO'zgartirish: <code>/ism Ismingiz</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    profile.name = parts[1].strip()[:60]
    save_profile(profile)
    await message.answer(f"Qabul qilindi, <b>{profile.name}</b>. Tanishganimdan xursandman.",
                         parse_mode=ParseMode.HTML)


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """JARVIS o'z holatini bildiradi: provayderlar, zanjir, limitlar."""
    def _mask(key) -> str:
        s = str(key or "")
        return f"✅ (•••{s[-4:]})" if len(s) > 4 else "❌"

    lines = [
        "<b>Holat</b>",
        f"Groq (tezlik): {_mask(settings.groq_api_key)}",
        f"OpenRouter (zaxira): {_mask(settings.openrouter_api_key)}",
        f"Gemini (uzun kontekst): {_mask(settings.gemini_api_key)}",
        f"OpenAI: {_mask(settings.openai_api_key)}",
        f"Local: <code>{settings.local_model}</code> (Ollama)",
        "Ovozli kirish: Whisper (Groq kaliti bilan, ovozli so'rovni tushunadi)",
        "Ovozli javob: o'chirilgan (javoblar matn + fayl shaklida)",
    ]
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@router.message(F.voice | F.audio)
async def on_voice(message: Message) -> None:
    """Ovozli xabar -> Whisper matn -> odatiy pipeline (javob matn+fayl)."""
    user_id = _get_user_id(message)
    if user_id is None:
        return
    if not settings.is_user_allowed(user_id):
        await message.answer("Ruxsat yo'q.")
        return
    if _rate_limited(user_id):
        await message.answer("Juda tez yuboryapsiz. 1 daqiqadan so'ng urinib ko'ring.")
        return
    if message.bot is None:
        return
    target = message.voice or message.audio
    if target is None:
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        from agent_bot.tools.voice import transcribe_voice

        buf = __import__("io").BytesIO()
        await message.bot.download(target, destination=buf)
        profile = load_profile(user_id)
        text = await transcribe_voice(buf.getvalue(), language=profile.language or None)
    except RuntimeError as exc:
        await message.answer(f"Ovozni matnga o'girib bo'lmadi: {exc}")
        return
    except Exception:
        logger.exception("Voice download/transcribe failed")
        await message.answer("Ovozli xabarni o'qib bo'lmadi.")
        return
    await message.answer(f"🎧 Eshitdim: <i>{text[:300]}</i>", parse_mode=ParseMode.HTML)
    await _send_result(message, user_id, text_override=text)


@router.message(F.text)
async def on_text(message: Message) -> None:
    if not message.text:
        return
    user_id = _get_user_id(message)
    if user_id is None:
        return

    if not settings.is_user_allowed(user_id):
        await message.answer("Ruxsat yo'q.")
        return
    if _rate_limited(user_id):
        await message.answer("Juda tez yuboryapsiz. 1 daqiqadan so'ng urinib ko'ring.")
        return

    # Matnli tasdiq: "tasdiqlayman" -> kutilayotgan amalni force bilan bajarish
    if message.text.strip().lower() in ("tasdiqlayman", "ha tasdiqlayman", "confirm"):
        pending = _pending_confirm.pop(user_id, None)
        if pending:
            try:
                result = await orchestrator.handle(user_id, pending, force=True)
            except Exception:
                logger.exception("Orchestrator crashed")
                await message.answer("Ichki xatolik.")
                return
            for chunk in result.chunks or [result.html]:
                await message.answer(chunk, parse_mode=ParseMode.HTML)
            return

    await _send_result(message, user_id)


@router.callback_query(F.data == "confirm:yes")
async def cb_confirm_yes(query: CallbackQuery) -> None:
    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        await query.answer()
        return
    pending = _pending_confirm.pop(user_id, None)
    await query.answer("Tasdiqlandi" if pending else "Kutilayotgan amal yo'q")
    if not pending or query.message is None or not isinstance(query.message, Message):
        return
    try:
        result = await orchestrator.handle(user_id, pending, force=True)
    except Exception:
        logger.exception("Orchestrator crashed")
        await query.message.answer("Ichki xatolik.")
        return
    for chunk in result.chunks or [result.html]:
        await query.message.answer(chunk, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "confirm:no")
async def cb_confirm_no(query: CallbackQuery) -> None:
    user_id = query.from_user.id if query.from_user else None
    if user_id is not None:
        _pending_confirm.pop(user_id, None)
    await query.answer("Bekor qilindi")
    if query.message is not None and isinstance(query.message, Message):
        await query.message.answer("Amal bekor qilindi.")


@router.callback_query(F.data.startswith("act:"))
async def cb_action(query: CallbackQuery) -> None:
    """Javob ostidagi inline tugmalar: fayl / yana variant / qisqartir."""
    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        await query.answer()
        return
    action = (query.data or "").split(":", 1)[1] if query.data else ""
    history = orchestrator.store.history(user_id)
    last_user = next((t for t in reversed(history) if t.role == "user"), None)
    last_ai = next((t for t in reversed(history) if t.role == "assistant"), None)
    if query.message is None or not isinstance(query.message, Message):
        await query.answer()
        return

    if action == "short":
        await query.answer()
        if last_ai:
            short = last_ai.text[:800] + ("…" if len(last_ai.text) > 800 else "")
            from agent_bot.telegram.formatting import markdown_to_telegram_html as _md

            await query.message.answer(_md(short), parse_mode=ParseMode.HTML)
        else:
            await query.message.answer("Qisqartiradigan javob topilmadi.")
    elif action == "more":
        await query.answer("Muqobil variantlar tayyorlanmoqda…")
        if last_user:
            await _send_result(query.message, user_id,
                               text_override=f"{last_user.text}\n\nIltimos, 3 ta muqobil variant ber.")
        else:
            await query.message.answer("Avval savol bering.")
    elif action == "file":
        await query.answer("Fayl tayyorlanmoqda…")
        if last_ai and last_user:
            from agent_bot.agents.orchestrator import IntentType as _IT

            files = orchestrator._maybe_build_file(_IT.DOCUMENT_GENERATION, last_user.text, last_ai.text)
            sent = False
            for f in files:
                if Path(f).exists():
                    await query.message.answer_document(FSInputFile(f))
                    sent = True
            if not sent:
                await query.message.answer("Fayl yaratib bo'lmadi.")
        else:
            await query.message.answer("Fayl qiladigan javob topilmadi.")
    else:
        await query.answer()


@router.message(F.photo)
async def on_photo(message: Message) -> None:
    """Foydalanuvchi yuborgan rasm, sxema yoki skrinshotni Gemini 3.8 Vision orqali ko'rib tahlil qilish."""
    user_id = _get_user_id(message)
    if user_id is None:
        return
    if not settings.is_user_allowed(user_id):
        await message.answer("Ruxsat yo'q.")
        return
    if _rate_limited(user_id):
        await message.answer("Juda tez yuboryapsiz. 1 daqiqadan so'ng urinib ko'ring.")
        return
    if message.bot is None or not message.photo:
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    photo = message.photo[-1]  # Eng yuqori sifatlisi
    caption = message.caption or "Ushbu tasvir, sxema yoki xatolikni chuqur tahlil qiling."

    try:
        from agent_bot.tools.vision_analyzer import VisionAnalyzer
        from google import genai

        temp_dir = settings.data_dir / "temp_photos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        img_path = temp_dir / f"{photo.file_id}.jpg"

        await message.bot.download(photo, destination=img_path)

        gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
        analyzer = VisionAnalyzer(gemini_client)
        vis_res = await analyzer.analyze_image(img_path, user_prompt=caption)

        if img_path.exists():
            img_path.unlink()

        if vis_res["success"]:
            from agent_bot.telegram.formatting import markdown_to_telegram_html as _md
            ans = f"👁️ <b>JARVIS VISION TAHLILI:</b>\n\n{_md(vis_res['text'])}"
            await message.answer(ans, parse_mode=ParseMode.HTML)
        else:
            await message.answer(f"❌ Rasmni tahlil qilishda xatolik: {vis_res.get('error')}")

    except Exception as exc:
        logger.exception("Photo analysis failed")
        await message.answer(f"❌ Rasmni o'qishda xatolik yuz berdi: {str(exc)}")


@router.message()
async def on_non_text(message: Message) -> None:
    """Matn bo'lmagan boshqa xabarlar (stiker/video) uchun javob."""
    user_id = _get_user_id(message)
    if user_id is None or not settings.is_user_allowed(user_id):
        return
    await message.answer(
        "Menga matn, rasm (sxema/chizma) yoki hujjat yuboring. Men uni tahlil qilib beraman."
    )

