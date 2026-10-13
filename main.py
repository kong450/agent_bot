"""Multi-Bot Entrypoint runner with resilient error handling and HTTP port binding."""
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
    "8952983428:AAGkvQcsQ3UURaHPiZdNLecDVc6XsiDmYhU",  # @EVloyiha_bot
    "8623266794:AAFdC9NfRi4cJIclgl6FSuPz-igtfOEao6w",  # @Metanolloyiha_bot
]

def get_tokens():
    env_tokens = os.environ.get("TELEGRAM_BOT_TOKENS", "").strip()
    if env_tokens:
        return [t.strip() for t in env_tokens.split(",") if t.strip()]
    single_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if single_token and single_token != "YOUR_BOT_TOKEN":
        return [single_token]
    return DEFAULT_TOKENS

async def handle_ping(request):
    return web.Response(text="JARVIS Agent Bot is LIVE and RUNNING! 🚀")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 HTTP Health server port {port} da faol!")

async def main():
    tokens = get_tokens()
    logger.info(f"⚡ Jami {len(tokens)} ta bot tekshirilmoqda...")

    # HTTP Health serverni Render uchun yoqish
    await start_web_server()

    dp = Dispatcher()
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    active_bots = []
    for token in tokens:
        bot = Bot(token=token)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            bot_info = await bot.get_me()
            logger.info(f"🚀 Bot muvaffaqiyatli ulandi: @{bot_info.username} (ID: {bot_info.id})")
            active_bots.append(bot)
        except Exception as e:
            logger.error(f"❌ Bot tokenida xatolik ({token[:15]}...): {e}")
            await bot.session.close()

    if not active_bots:
        logger.error("❌ Birorta ham faol bot topilmadi!")
        return

    try:
        logger.info(f"⚡ {len(active_bots)} ta bot bir vaqtda parallel polling rejimida ishlamoqda...")
        await dp.start_polling(*active_bots, handle_signals=False)
    finally:
        for bot in active_bots:
            await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Botlar to'xtatildi.")
