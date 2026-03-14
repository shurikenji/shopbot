"""Quick verification script for Phase 2."""
import asyncio
from db.models import init_db
from db.database import close_db


async def main():
    await init_db()

    # Test imports
    from bot.services.newapi import get_groups, create_token, search_token, update_token, get_token_quota
    print("[OK] newapi.py — 5 functions imported")

    from bot.services.mbbank import fetch_transactions, extract_order_code, _parse_amount
    print("[OK] mbbank.py — 3 functions imported")

    # Test extract_order_code
    assert extract_order_code("Chuyen tien ORD1A2B3C4D thanh toan") == "ORD1A2B3C4D"
    assert extract_order_code("Random text") is None
    assert extract_order_code("abc ord12345678 xyz") == "ORD12345678"
    print("[OK] extract_order_code: all cases pass")

    # Test _parse_amount
    assert _parse_amount("3000") == 3000
    assert _parse_amount("1,000,000") == 1000000
    assert _parse_amount("0") == 0
    print("[OK] _parse_amount: all cases pass")

    from bot.services.vietqr import build_qr_url, build_qr_caption
    print("[OK] vietqr.py — 2 functions imported")

    from bot.services.payment_poller import start_payment_poller, process_wallet_payment
    print("[OK] payment_poller.py — 2 public functions imported")

    from bot.middlewares.auth import AuthMiddleware
    print("[OK] auth.py — AuthMiddleware imported")

    # Test QR URL build
    url = await build_qr_url(31000, "ORD12345678")
    assert "vietqr.io" in url
    assert "31000" in url
    assert "ORD12345678" in url
    print(f"[OK] QR URL: {url[:80]}...")

    # Test QR caption
    caption = await build_qr_caption(31000, "ORD12345678")
    assert "31.000₫" in caption
    assert "ORD12345678" in caption
    print("[OK] QR caption builds correctly")

    await close_db()
    print("\n=== ALL PHASE 2 TESTS PASSED ===")


asyncio.run(main())
