"""
bot/handlers/__init__.py — setup_routers() → include tất cả sub-routers.
"""
from __future__ import annotations

from aiogram import Dispatcher


def setup_routers(dp: Dispatcher) -> None:
    """Đăng ký tất cả routers vào dispatcher."""
    from bot.handlers.start import router as start_router
    from bot.handlers.catalog import router as catalog_router
    from bot.handlers.flow_api_key import router as flow_api_key_router
    from bot.handlers.flow_accounts import router as flow_accounts_router
    from bot.handlers.wallet import router as wallet_router
    from bot.handlers.orders import router as orders_router
    from bot.handlers.search_order import router as search_order_router
    from bot.handlers.account import router as account_router
    from bot.handlers.support import router as support_router

    dp.include_routers(
        start_router,
        flow_accounts_router,  # FSM states trước catalog
        catalog_router,
        flow_api_key_router,
        wallet_router,
        orders_router,
        search_order_router,
        account_router,
        support_router,
    )
