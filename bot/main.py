"""
bot/main.py — Entry point: khởi bot + payment poller + admin server.
Chạy: python -m bot.main
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import setup_routers
from bot.middlewares.auth import AuthMiddleware
from db.models import init_db
from db.database import close_db
from bot.services.payment_poller import start_payment_poller

# ── Logging setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Khởi động bot, poller, và admin server."""

    # 1. Validate config
    if not settings.bot_token:
        logger.error("BOT_TOKEN chưa được cấu hình trong .env")
        return

    logger.info("Starting ShopBot...")

    # 2. Init database
    await init_db()
    logger.info("Database initialized")

    # 3. Create bot + dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Register middleware (chạy trước mọi handler)
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # 5. Setup routers (tất cả handlers)
    setup_routers(dp)

    # 5.5 Setup Bot Commands (Hiện menu góc trái)
    commands = [
        BotCommand(command="products", description="🛒 Sản phẩm"),
        BotCommand(command="wallet", description="👛 Ví của tôi"),
        BotCommand(command="orders", description="📋 Lịch sử đơn hàng"),
        BotCommand(command="search", description="🔎 Tìm đơn hàng"),
        BotCommand(command="profile", description="👤 Thông tin tài khoản"),
        BotCommand(command="support", description="🆘 Hỗ trợ"),
    ]
    await bot.set_my_commands(commands)

    # 6. Start payment poller (background task)
    poller_task = asyncio.create_task(start_payment_poller(bot))

    # 7. Start admin panel (nếu có)
    admin_task = None
    try:
        from admin.app import create_admin_app
        import uvicorn

        admin_app = create_admin_app()
        config = uvicorn.Config(
            admin_app,
            host="0.0.0.0",
            port=settings.admin_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        admin_task = asyncio.create_task(server.serve())
        logger.info("Admin panel starting on port %d", settings.admin_port)
    except ImportError:
        logger.warning("Admin panel not available (Phase 4 not built yet)")
    except Exception as e:
        logger.warning("Admin panel failed to start: %s", e)

    # 8. Start polling (blocking)
    try:
        logger.info("Bot started — polling for updates...")
        await dp.start_polling(bot)
    finally:
        # Cleanup
        logger.info("Shutting down...")
        poller_task.cancel()
        if admin_task:
            admin_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
        if admin_task:
            try:
                await admin_task
            except asyncio.CancelledError:
                pass
        await close_db()
        await bot.session.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
