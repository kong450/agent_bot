"""Entrypoint runner for Agent Bot."""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from agent_bot.config.settings import settings
from agent_bot.telegram.handlers import router, orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    if not settings.telegram_bot_token or settings.telegram_bot_token == "YOUR_BOT_TOKEN":
        logger.error(
            "\n"
            "====================================================================\n"
            "❌ XATOLIK: TELEGRAM_BOT_TOKEN kiritilmagan!\n"
            "Iltimos, C:\\Users\\user\\Desktop\\agent_bot\\.env faylini oching va\n"
            "TELEGRAM_BOT_TOKEN=... qatoriga BotFather'dan olgan tokeningizni yozing.\n"
            "====================================================================\n"
        )
        return

    logger.info("⚡ AGENT BOT ishga tushirilmoqda...")
    # Yagona runtime miya — handlers ichidagi instance (ikkinchi nusxa yaratilmaydi)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    # Orchestratorni barcha handlerlarga dependency injection orqali uzatish
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    try:
        logger.info("🚀 Polling boshlandi. Bot Telegramda faol!")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
