"""Multi-Bot Entrypoint runner: runs both @EVloyiha_bot and @Metanolloyiha_bot concurrently."""
import asyncio
import logging
import sys
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

# Ikkala bot tokenlari ro'yxati
BOT_TOKENS = [
    "8952983428:AAFQKWOUG_l79PVLU8SPQAtajMLVF1iHpoE",  # @EVloyiha_bot
    "8623266794:AAHOhvYTv0SIKOJMC7H2qevOvw62abV01n0",  # @Metanolloyiha_bot
]

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
    logger.info("⚡ AGENT BOT DUAL-PLATFORM (JARVIS) ishga tushirilmoqda...")

    # Yagona boshqaruvchi Dispatcher va uning marshruti
    dp = Dispatcher()
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    # Ikkala botni bitta jarayonda parallel polling rejimida ishlatish
    tasks = [start_single_bot(t, dp) for t in BOT_TOKENS]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Barcha botlar to'xtatildi.")
