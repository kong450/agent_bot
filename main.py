"""Multi-Bot Entrypoint runner with resilient error handling and HTTP port binding."""
import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()

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

# XAVFSIZLIK: jonli tokenni bu yerga HECH QACHON yozmang (git tarixiga tushadi).
# Tokenlar faqat environment'dan o'qiladi:
#   TELEGRAM_BOT_TOKENS="tok1,tok2"  (bir nechta bot)
#   TELEGRAM_BOT_TOKEN="tok1"        (bitta bot)
DEFAULT_TOKENS: list = []


def get_tokens():
    env_tokens = os.environ.get("TELEGRAM_BOT_TOKENS", "").strip()
    if env_tokens:
        return [t.strip() for t in env_tokens.split(",") if t.strip()]
    single_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if single_token and single_token != "YOUR_BOT_TOKEN":
        return [single_token]
    return list(DEFAULT_TOKENS)

async def handle_ping(request):
    return web.Response(text="JARVIS Agent Bot is LIVE and RUNNING! 🚀")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"🌐 HTTP Health server port {port} da faol!")
    except Exception as e:
        logger.warning(f"HTTP server port {port} ochilmadi (ehtimol band): {e}")

async def _keep_alive_loop():
    """Render bepul tarifida 15 daqiqada uxlab qolmasligi uchun har 8 daqiqada ping yuboradi."""
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if not render_url:
        return
    logger.info(f"🔄 Render Keep-Alive ping faollashtirildi: {render_url}")
    await asyncio.sleep(60.0)
    import aiohttp
    while True:
        try:
            target = f"{render_url}/health" if not render_url.endswith("/health") else render_url
            async with aiohttp.ClientSession() as session:
                async with session.get(target, timeout=aiohttp.ClientTimeout(total=15.0)) as resp:
                    logger.info(f"⚡ Keep-alive ping muvaffaqiyatli: {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping xatosi: {e}")
        await asyncio.sleep(480.0)

from aiogram.client.session.aiohttp import AiohttpSession

def create_bot(token: str) -> Bot:
    """Windows va uzoq kutishlarda [WinError 64] bo'lmasligi uchun xavfsiz session."""
    session = AiohttpSession(timeout=20.0)
    session._connector_init["force_close"] = True
    session._connector_init["enable_cleanup_closed"] = True
    return Bot(token=token, session=session)

async def main():
    # 1. HTTP Health serverni Render uchun darhol yoqish (Render health check yiqilmasligi uchun)
    await start_web_server()
    # 2. Render uxlab qolmasligi uchun avtomatik fon pingi
    asyncio.create_task(_keep_alive_loop())

    dp = Dispatcher()
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    while True:
        tokens = get_tokens()
        if not tokens:
            logger.error(
                "TELEGRAM_BOT_TOKENS yoki TELEGRAM_BOT_TOKEN topilmadi. "
                "Render Environment bo'limida belgilang. 15 soniyadan so'ng qayta tekshiriladi..."
            )
            await asyncio.sleep(15.0)
            continue

        active_bots = []
        for token in tokens:
            bot = create_bot(token)
            try:
                try:
                    await asyncio.wait_for(bot.delete_webhook(drop_pending_updates=False), timeout=5.0)
                except Exception as we:
                    logger.warning(f"delete_webhook ogohlantirish: {we}")
                bot_info = await asyncio.wait_for(bot.get_me(), timeout=8.0)
                logger.info(f"🚀 Bot muvaffaqiyatli ulandi: @{bot_info.username} (ID: {bot_info.id})")
                active_bots.append(bot)
            except Exception as e:
                logger.error(f"❌ Bot tokenida xatolik ({token[:15]}...): {e}")
                await bot.session.close()

        if not active_bots:
            logger.error("❌ Birorta ham faol bot topilmadi! Tokenlarni tekshiring. 20 soniyadan so'ng qayta urinadi...")
            await asyncio.sleep(20.0)
            continue

        try:
            logger.info(f"⚡ {len(active_bots)} ta bot parallel polling rejimida ishlamoqda...")
            await dp.start_polling(*active_bots, handle_signals=False, polling_timeout=15)
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            logger.error(f"⚠️ Polling uzildi: {e}. 5 soniyadan so'ng qayta ulanadi...")
            await asyncio.sleep(5.0)
        finally:
            for bot in active_bots:
                try:
                    await bot.session.close()
                except Exception:
                    pass

    for bot in active_bots:
        try:
            await bot.session.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Botlar to'xtatildi.")
