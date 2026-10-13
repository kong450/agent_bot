"""Multi-Bot Entrypoint runner: runs both @EVloyiha_bot and @Metanolloyiha_bot concurrently."""
import asyncio
import logging
import sys
import os
from typing import List
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from agent_bot.config.settings import settings
from agent_bot.telegram.handlers import router, orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Standart ikkala bot tokenlari (Koyeb Environment Variables orqali ham o'qiladi)
DEFAULT_TOKENS = [
    "8952983428:AAFQKWOUG_l79PVLU8SPQAtajMLVF1iHpoE",  # @EVloyiha_bot
    "8623266794:AAHOhvYTv0SIKOJMC7H2qevOvw62abV01n0",  # @Metanolloyiha_bot
]

def get_tokens() -> List[str]:
    env_tokens = os.environ.get("TELEGRAM_BOT_TOKENS", "").strip()
    if env_tokens:
        return [t.strip() for t in env_tokens.split(",") if t.strip()]
    single_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if single_token and single_token != "YOUR_BOT_TOKEN":
        return [single_token]
    return DEFAULT_TOKENS

async def start_single_bot(token: str, dp: Dispatcher):
    """Bitta botni xavfsiz ishga tushirish."""
    bot = Bot(token=token)
    try:
        bot_info = await bot.get_me()
        logger.info(f"🚀 Bot faollashdi: @{bot_info.username} ({bot_info.first_name})")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Botda xatolik ({token[:10]}...): {e}")
    finally:
        await bot.session.close()

async def main():
    tokens = get_tokens()
    logger.info(f"⚡ AGENT BOT DUAL-PLATFORM: {len(tokens)} ta bot ishga tushirilmoqda...")

    dp = Dispatcher()
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    tasks = [start_single_bot(t, dp) for t in tokens]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Barcha botlar to'xtatildi.")
