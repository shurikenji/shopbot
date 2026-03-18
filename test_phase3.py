"""Quick verification script for Phase 3."""
import asyncio
from db.models import init_db
from db.database import close_db


async def main():
    await init_db()

    # Test active handler imports
    from bot.handlers.start import router as r1
    print(f"[OK] start.py — router name: {r1.name}")

    from bot.handlers.catalog import router as r2
    print(f"[OK] catalog.py — router name: {r2.name}")

    from bot.handlers.flow_api_key import router as r3
    print(f"[OK] flow_api_key.py — router name: {r3.name}")

    from bot.handlers.flow_accounts import router as r4
    print(f"[OK] flow_accounts.py — router name: {r4.name}")

    from bot.handlers.wallet import router as r5
    print(f"[OK] wallet.py — router name: {r5.name}")

    from bot.handlers.orders import router as r6
    print(f"[OK] orders.py — router name: {r6.name}")

    from bot.handlers.search_order import router as r7
    print(f"[OK] search_order.py — router name: {r7.name}")

    from bot.handlers.account import router as r8
    print(f"[OK] account.py — router name: {r8.name}")

    from bot.handlers.support import router as r9
    print(f"[OK] support.py — router name: {r9.name}")

    # Test setup_routers
    from aiogram import Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())
    from bot.handlers import setup_routers
    setup_routers(dp)
    print(f"[OK] setup_routers — {len(dp.sub_routers)} routers registered")

    # Test FSM states exist
    from bot.handlers.flow_api_key import ApiKeyStates
    from bot.handlers.flow_accounts import UpgradeStates
    from bot.handlers.wallet import WalletTopupStates
    from bot.handlers.search_order import SearchOrderStates
    print(f"[OK] FSM States: ApiKeyStates, UpgradeStates, WalletTopupStates, SearchOrderStates")

    # Test main.py imports
    from bot.main import main as main_func
    print(f"[OK] main.py — main() function importable")

    await close_db()
    print("\n=== ALL PHASE 3 TESTS PASSED ===")


asyncio.run(main())
