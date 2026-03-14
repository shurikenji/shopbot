"""Quick verification script for Phase 1."""
import asyncio
from db.database import get_db, close_db
from db.models import init_db
from bot.utils.order_code import generate_order_code
from bot.utils.formatting import format_vnd, mask_api_key, status_emoji
from bot.callback_data.factories import (
    CategoryPageCB, CategorySelectCB, KeyActionCB,
    ServerSelectCB, ProductPageCB, ProductSelectCB,
    PaymentMethodCB, OrderCancelCB, MyKeySelectCB,
    MyKeyInputCB, WalletActionCB, WalletTopupAmountCB,
    OrderListPageCB, OrderDetailCB, BackCB,
)
from bot.keyboards.reply_kb import main_menu_kb
from bot.keyboards.inline_kb import categories_kb, payment_method_kb


async def main():
    # Test DB init
    await init_db()
    db = await get_db()

    # Verify all tables exist
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in await cursor.fetchall()]
    expected = [
        "api_servers", "categories", "chatgpt_accounts", "logs",
        "orders", "processed_transactions", "products", "settings",
        "user_keys", "users", "wallet_transactions", "wallets",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"
    print(f"[OK] All {len(expected)} tables created: {', '.join(expected)}")

    # Verify default settings
    cursor = await db.execute("SELECT COUNT(*) FROM settings")
    count = (await cursor.fetchone())[0]
    assert count >= 17, f"Expected 17+ settings, got {count}"
    print(f"[OK] {count} default settings inserted")

    # Test utilities
    code = generate_order_code()
    assert code.startswith("ORD") and len(code) == 11
    print(f"[OK] Order code: {code}")
    print(f"[OK] Format VND: {format_vnd(31000)}")
    print(f"[OK] Mask key: {mask_api_key('sk-abcdefghijklmnop')}")
    print(f"[OK] Status emoji: {status_emoji('completed')}")

    # Test callback data packing/unpacking
    cb = CategorySelectCB(id=5)
    packed = cb.pack()
    assert len(packed) <= 64, f"Callback too long: {len(packed)}"
    print(f"[OK] Callback pack: {packed}")

    # Test reply keyboard
    kb = main_menu_kb()
    assert len(kb.keyboard) == 3
    print("[OK] Reply keyboard: 3 rows, 6 buttons")

    await close_db()
    print("\n=== ALL PHASE 1 TESTS PASSED ===")


asyncio.run(main())
