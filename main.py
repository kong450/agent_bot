"""Multi-Bot Entrypoint runner with lightweight HTTP port binding for Render Web Service."""
import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from agent_bot.config.settings import settings
from agent_bot.telegram.handlers import router, orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_TOKENS = [
    "8952983428:AAFQKWOUG_l79PVLU8SPQAtajMLVF1iHpoE",  # @EVloyiha_bot
    "8623266794:AAHOhvYTv0SIKOJMC7H2qevOvw62abV01n0",  # @Metanolloyiha_bot
]

def get_tokens():
    env_tokens = os.environ.get("TELEGRAM_BOT_TOKENS", "").strip()
    if env_tokens:
        return [t.strip() for t in env_tokens.split(",") if t.strip()]
    single_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if single_token and single_token != "YOUR_BOT_TOKEN":
        return [single_token]
    return DEFAULT_TOKENS

async def start_single_bot(token: str):
    """Har bir bot uchun alohida Dispatcher va session yaratish (No Conflict)."""
    bot = Bot(token=token)
    dp = Dispatcher()
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    try:
        # Eski to'qnashuvlarni tozalash
        await bot.delete_webhook(drop_pending_updates=True)
        bot_info = await bot.get_me()
        logger.info(f"🚀 Bot muvaffaqiyatli ishga tushdi: @{bot_info.username}")
        await dp.start_polling(bot, handle_signals=False)
    except Exception as e:
        logger.error(f"Botda xatolik ({token[:10]}...): {e}")
    finally:
        await bot.session.close()

async def handle_ping(request):
    return web.Response(text="JARVIS Agent Bot is LIVE and HEALTHY! 🚀")

async def start_web_server():
    """Render Web Service 'No open ports detected' xatosini yo'qotish uchun HTTP server."""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 HTTP Health server port {port} da ishga tushdi!")

async def main():
    tokens = get_tokens()
    logger.info(f"⚡ DUAL-PLATFORM: {len(tokens)} ta bot ishga tushirilmoqda...")

    # 1. Render portini darhol ochish
    await start_web_server()

    # 2. Botlarni parallel yurgazish
    bot_tasks = [start_single_bot(t) for t in tokens]
    await asyncio.gather(*bot_tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Botlar to'xtatildi.")
