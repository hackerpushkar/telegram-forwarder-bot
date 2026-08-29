import asyncio
import logging
import sys
from pathlib import Path

# Configure UTF-8 for console output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import config
from bot.database.db import init_db
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.album import AlbumMiddleware
from bot.handlers import get_main_router
from bot.services.userbot import userbot_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Open main dashboard"),
        BotCommand(command="newroute", description="➕ Create a forwarding route (5 steps)"),
        BotCommand(command="routes", description="📋 View & manage all routes"),
        BotCommand(command="userbot", description="👤 Manage Telegram Userbot account"),
        BotCommand(command="stats", description="📊 View bot throughput & statistics"),
        BotCommand(command="ping", description="🏓 Check latency & health"),
        BotCommand(command="help", description="📖 Setup guide & instructions"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully with Telegram")
    except Exception as e:
        logger.warning("Failed to register bot commands: %s", e)

async def main():
    logger.info("Starting Super Telegram Forwarder Bot (Hybrid Bot + Userbot)...")

    # 1. Initialize SQLite Database
    await init_db()

    # 2. Validate Token
    if not config.BOT_TOKEN or config.BOT_TOKEN == "your_bot_token_here":
        logger.error(
            "\n"
            "===============================================================\n"
            "[ERROR] BOT_TOKEN is missing or not set in your .env file!\n"
            "Please create a .env file (or copy from .env.example) and add:\n"
            "BOT_TOKEN=your_actual_bot_token_from_botfather\n"
            "==============================================================="
        )
        sys.exit(1)

    # 3. Create Bot and Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Attach bot instance to userbot manager
    userbot_manager.bot = bot

    # 4. Register Middlewares
    album_middleware = AlbumMiddleware(latency=0.6)
    dp.message.middleware(album_middleware)
    dp.channel_post.middleware(album_middleware)

    auth_middleware = AuthMiddleware()
    dp.message.outer_middleware(auth_middleware)
    dp.callback_query.outer_middleware(auth_middleware)

    # 5. Include Routers
    main_router = get_main_router()
    dp.include_router(main_router)

    # 6. Initialize Userbot Client in Background
    try:
        await userbot_manager.initialize()
    except Exception as ub_err:
        logger.warning("Userbot initialization warning: %s", ub_err)

    # 7. Set My Commands & Start Polling
    await setup_bot_commands(bot)
    
    # Drop pending updates on startup to avoid flood on restart
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is ready and polling for updates!")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "channel_post", "callback_query", "edited_message", "edited_channel_post"]
        )
    finally:
        await bot.session.close()
        if userbot_manager.client and userbot_manager.client.is_connected():
            await userbot_manager.client.disconnect()
        logger.info("Bot stopped cleanly.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot exited.")
