"""
bot/services/payment_poller.py — Background task chạy liên tục.
Poll MBBank → match giao dịch với đơn hàng pending → xử lý → expire đơn quá hạn.
"""
from __future__ import annotations

import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot

from bot.config import settings as env_settings
from bot.services.mbbank import fetch_transactions, extract_order_code
from bot.services.api_clients import get_api_client
from bot.utils.formatting import format_vnd, mask_api_key, quota_to_dollar
from db.queries.orders import (
    get_pending_qr_orders,
    get_order_by_code,
    get_order_by_id,
    update_order_status,
    mark_refunded,
)
from db.queries.transactions import is_transaction_processed, mark_transaction_processed
from db.queries.settings import get_setting, get_setting_int
from db.queries.wallets import add_balance
from db.queries.products import get_product_by_id, decrement_stock
from db.queries.servers import get_server_by_id
from db.queries.user_keys import create_user_key
from db.queries.account_stocks import get_available_account, mark_account_sold
from db.queries.logs import add_log

logger = logging.getLogger(__name__)


async def start_payment_poller(bot: Bot) -> None:
    """
    Entry point: chạy poller loop vô hạn.
    Gọi hàm này bằng asyncio.create_task() khi khởi bot.
    """
    logger.info("Payment poller started")
    await add_log("Payment poller started", module="poller")

    while True:
        try:
            poll_interval = await get_setting_int("poll_interval", env_settings.poll_interval)
            await _poll_cycle(bot)
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Payment poller cancelled")
            break
        except Exception as e:
            logger.error("Poller error: %s", e, exc_info=True)
            await add_log(f"Poller error: {e}", level="error", module="poller")
            await asyncio.sleep(15)


async def _poll_cycle(bot: Bot) -> None:
    """Một chu kỳ poll: lấy giao dịch → match → xử lý → expire."""

    # 1. Expire đơn quá hạn trước
    await _expire_old_orders(bot)

    # 2. Lấy đơn pending QR
    pending_orders = await get_pending_qr_orders()
    if not pending_orders:
        return

    # 3. Fetch giao dịch MBBank
    transactions = await fetch_transactions()
    if not transactions:
        return

    # 4. Match từng giao dịch với đơn hàng
    for tx in transactions:
        tx_id = tx["transactionID"]

        # Dedup: bỏ qua giao dịch đã xử lý
        if await is_transaction_processed(tx_id):
            continue

        # Trích xuất mã đơn hàng từ nội dung chuyển khoản
        order_code = extract_order_code(tx["description"])
        if not order_code:
            continue

        # Tìm đơn hàng match
        order = await get_order_by_code(order_code)
        if not order:
            continue

        # Kiểm tra đơn còn pending
        if order["status"] != "pending":
            await mark_transaction_processed(tx_id, order_code, tx["amount"])
            continue

        # Kiểm tra số tiền khớp
        if tx["amount"] != order["amount"]:
            logger.warning(
                "Amount mismatch for %s: expected %d, got %d",
                order_code, order["amount"], tx["amount"],
            )
            continue

        # Match thành công → xử lý
        logger.info("Matched tx %s → order %s (amount=%d)", tx_id, order_code, tx["amount"])
        # Cập nhật trạng thái paid
        await update_order_status(
            order["id"], "paid",
            mb_transaction_id=tx_id,
            paid_at=datetime.utcnow().isoformat(),
        )

        # Đánh dấu đã xử lý giao dịch MBBank
        await mark_transaction_processed(tx_id, order_code, tx["amount"])

        # Xử lý đơn hàng
        await _process_order(bot, order)


async def _process_order(bot: Bot, order: dict) -> None:
    """
    Xử lý đơn hàng sau khi thanh toán thành công.
    Tùy product_type: tạo key mới, nạp key cũ, giao ChatGPT.
    """
    order_id = order["id"]
    user_id = order["user_id"]
    product_type = order["product_type"]
    order_code = order["order_code"]

    await update_order_status(order_id, "processing")

    try:
        if product_type == "key_new":
            await _process_key_new(bot, order)
        elif product_type == "key_topup":
            await _process_key_topup(bot, order)
        elif product_type == "account_stocked":
            await _process_account_stocked(bot, order)
        elif product_type == "service_upgrade":
            # Upgrade: admin xử lý qua admin panel hoặc live chat
            await update_order_status(order_id, "processing")
            user_input = order.get("user_input_data") or ""
            input_line = f"\n📝 Thông tin KH: <code>{user_input}</code>" if user_input else ""
            
            from db.queries.settings import get_setting
            from db.queries.users import get_user_by_id
            support_url = await get_setting("support_url", "https://t.me/admin")

            await _notify_user(
                bot, user_id,
                f"✅ Đơn <b>{order_code}</b> đã thanh toán!\n"
                f"⏳ Admin đang xử lý đơn hàng của bạn.{input_line}\n\n"
                f"💬 Nếu cần hỗ trợ gấp hoặc trao đổi thông tin, vui lòng inbox Admin tại: {support_url}"
            )
            
            user = await get_user_by_id(user_id)
            contact_line = ""
            if user and user.get("telegram_id"):
                contact_line = f"\n👉 <a href='tg://user?id={user['telegram_id']}'>💬 Bấm vào đây để inbox Khách</a>"

            await _notify_admins(
                bot,
                f"📦 Đơn <b>{order_code}</b> cần xử lý!\n"
                f"Loại: <b>service_upgrade</b>\n"
                f"Product: {order.get('product_name', 'N/A')}"
                f"{input_line}{contact_line}"
            )
            return
        elif product_type == "wallet_topup":
            await _process_wallet_topup(bot, order)
        else:
            logger.error("Unknown product_type: %s for order %s", product_type, order_code)
            await _refund_order(bot, order, f"Loại sản phẩm không hợp lệ: {product_type}")
            return

    except Exception as e:
        logger.error("Process order %s failed: %s", order_code, e, exc_info=True)
        await add_log(
            f"Process order {order_code} failed: {e}",
            level="error", module="poller",
        )
        await _refund_order(bot, order, f"Lỗi xử lý: {e}")


async def _process_key_new(bot: Bot, order: dict) -> None:
    """Tạo API key mới trên server."""
    server = await get_server_by_id(order["server_id"])
    if not server:
        await _refund_order(bot, order, "Server không tồn tại")
        return

    product = await get_product_by_id(order["product_id"]) if order.get("product_id") else None
    if not product and not order.get("custom_quota"):
        await _refund_order(bot, order, "Sản phẩm không tồn tại")
        return

    # Tạo tên token ngẫu nhiên
    token_name = "key_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    # Quota: ưu tiên custom_quota từ order (khi user nhập $ tùy chọn)
    quota = order.get("custom_quota") or (product["quota_amount"] if product else 0)
    group_name = order.get("group_name") or (product.get("group_name") if product else "") or ""

    # Get API client based on server type
    client = get_api_client(server)

    # Gọi API tạo token
    result = await client.create_token(
        server=server,
        quota=quota,
        group=group_name,
        name=token_name,
    )

    if not result:
        await _refund_order(bot, order, "Không thể tạo key trên server")
        return

    # Lấy key từ response
    api_key = result.get("key", "")
    if not api_key and isinstance(result, dict):
        # Try nested data
        api_key = result.get("data", {}).get("key", "") if isinstance(result.get("data"), dict) else ""

    # Nếu response không chứa key → search bằng name
    if not api_key:
        logger.warning("create_token didn't return key, searching by name: %s", token_name)
        await asyncio.sleep(1)  # Đợi server xử lý xong
        found = await client.search_token_by_name(server, token_name)
        if found:
            api_key = found.get("key", "")
            logger.info("Found key by name search: %s", api_key[:20] if api_key else "empty")

    if not api_key:
        await _refund_order(bot, order, "API không trả về key")
        return

    # Thêm prefix sk- nếu chưa có
    full_key = api_key if api_key.startswith("sk-") else f"sk-{api_key}"

    # Lưu key vào user_keys
    await create_user_key(
        user_id=order["user_id"],
        server_id=server["id"],
        api_key=full_key,
        label=mask_api_key(full_key),
    )

    # Cập nhật order
    await update_order_status(
        order["id"], "completed",
        api_key=full_key,
        quota_after=quota,
    )

    await add_log(
        f"Key mới tạo cho order {order['order_code']}: {mask_api_key(full_key)}",
        module="poller",
    )

    # Thông báo user — dùng template từ DB
    mult = server.get("quota_multiple", 1.0)
    dollar_str = quota_to_dollar(quota, mult)
    tpl = await get_setting(
        "msg_key_new",
        "\u2705 Đơn {order_code} hoàn thành!\n\n"
        "🔑 API Key của bạn:\n{api_key}\n\n"
        "💵 Số dư: {dollar}\n"
        "🖥 Server: {server}\n\n"
        "⚠️ Vui lòng lưu key cẩn thận!"
    )
    msg = tpl.format(
        order_code=f"<b>{order['order_code']}</b>",
        api_key=f"<code>{full_key}</code>",
        dollar=f"<b>{dollar_str}</b>",
        server=f"<b>{server['name']}</b>",
    )
    await _notify_user(bot, order["user_id"], msg)


async def _process_key_topup(bot: Bot, order: dict) -> None:
    """Nạp thêm quota cho key hiện có."""
    server = await get_server_by_id(order["server_id"])
    if not server:
        await _refund_order(bot, order, "Server không tồn tại")
        return

    product = await get_product_by_id(order["product_id"]) if order.get("product_id") else None
    if not product and not order.get("custom_quota"):
        await _refund_order(bot, order, "Sản phẩm không tồn tại")
        return

    existing_key = order.get("existing_key", "")
    if not existing_key:
        await _refund_order(bot, order, "Không có key để nạp")
        return

    # Get API client based on server type
    client = get_api_client(server)

    # Search token hiện tại trên server
    token_data = await client.search_token(server, existing_key)
    if not token_data:
        await _refund_order(bot, order, "Không tìm thấy key trên server")
        return

    token_id = token_data["id"]
    current_quota = token_data.get("remain_quota", 0)
    # Quota: ưu tiên custom_quota từ order
    add_quota = order.get("custom_quota") or (product["quota_amount"] if product else 0)
    new_quota = current_quota + add_quota

    # Update quota - use build_update_payload to preserve all fields
    result = await client.update_token(
        server=server,
        token_id=token_id,
        new_quota=new_quota,
        current_data=token_data,
    )

    if not result:
        await _refund_order(bot, order, "Không thể cập nhật quota trên server")
        return

    # Lưu/cập nhật key vào danh sách key của user
    from db.queries.user_keys import upsert_user_key
    await upsert_user_key(
        user_id=order["user_id"],
        server_id=server["id"],
        api_key=existing_key,
        api_token_id=token_id,
        label=mask_api_key(existing_key),
    )

    # Cập nhật order
    await update_order_status(
        order["id"], "completed",
        api_key=existing_key,
        api_token_id=token_id,
        quota_before=current_quota,
        quota_after=new_quota,
    )

    await add_log(
        f"Topup key cho order {order['order_code']}: "
        f"{mask_api_key(existing_key)} quota {current_quota:,} → {new_quota:,}",
        module="poller",
    )

    # Thông báo user — dùng template từ DB
    mult = server.get("quota_multiple", 1.0)
    before_dollar = quota_to_dollar(current_quota, mult)
    add_dollar = quota_to_dollar(add_quota, mult)
    after_dollar = quota_to_dollar(new_quota, mult)
    tpl = await get_setting(
        "msg_key_topup",
        "✅ Đơn {order_code} hoàn thành!\n\n"
        "🔑 Key: {api_key}\n"
        "💵 Số dư trước: {dollar_before}\n"
        "💵 Nạp thêm: +{dollar_added}\n"
        "💵 Số dư sau: {dollar_after}"
    )
    msg = tpl.format(
        order_code=f"<b>{order['order_code']}</b>",
        api_key=f"<code>{mask_api_key(existing_key)}</code>",
        dollar_before=f"<b>{before_dollar}</b>",
        dollar_added=f"<b>{add_dollar}</b>",
        dollar_after=f"<b>{after_dollar}</b>",
    )
    await _notify_user(bot, order["user_id"], msg)


async def _process_account_stocked(bot: Bot, order: dict) -> None:
    """Giao tài khoản từ kho chung (account_stocks) — hỗ trợ format_template."""
    product_id = order.get("product_id")
    if not product_id:
        await _refund_order(bot, order, "Sản phẩm không hợp lệ")
        return

    product = await get_product_by_id(product_id)

    # Lấy tài khoản HỆ THỐNG ĐÃ XÍ CHỖ cho đơn hàng này từ trước
    from db.queries.account_stocks import get_reserved_account
    account = await get_reserved_account(order["id"])
    if not account:
        await _refund_order(bot, order, "Tài khoản giữ chỗ không tồn tại (Lỗi kho)")
        return

    # Đánh dấu đã bán
    await mark_account_sold(
        account["id"], order["user_id"], order["id"],
        product_id=product_id,
    )

    # Format hiển thị theo template
    raw_data = account["account_data"]
    fmt_template = product.get("format_template") if product else None

    if fmt_template and "|" in raw_data:
        labels = [l.strip() for l in fmt_template.split("|")]
        values = [v.strip() for v in raw_data.split("|")]
        display_lines = []
        for i, label in enumerate(labels):
            val = values[i] if i < len(values) else "—"
            display_lines.append(f"  {label}: <code>{val}</code>")
        formatted_data = "\n".join(display_lines)
    else:
        formatted_data = f"<code>{raw_data}</code>"

    # Cập nhật order
    await update_order_status(
        order["id"], "completed",
        delivery_info=raw_data,
    )

    await add_log(
        f"Account delivered for order {order['order_code']}",
        module="poller",
    )

    msg = (
        f"✅ Đơn <b>{order['order_code']}</b> hoàn thành!\n\n"
        f"📦 Thông tin tài khoản:\n{formatted_data}\n\n"
        f"⚠️ Vui lòng lưu thông tin cẩn thận!"
    )
    await _notify_user(bot, order["user_id"], msg)


async def _process_wallet_topup(bot: Bot, order: dict) -> None:
    """Nạp tiền vào ví nội bộ."""
    amount = order["amount"]
    user_id = order["user_id"]

    new_balance = await add_balance(
        user_id=user_id,
        amount=amount,
        tx_type="topup",
        reference_id=order["order_code"],
        description=f"Nạp ví qua QR - {order['order_code']}",
    )

    await update_order_status(order["id"], "completed")

    await add_log(
        f"Wallet topup {format_vnd(amount)} for order {order['order_code']}",
        module="poller",
    )

    tpl = await get_setting(
        "msg_wallet_topup",
        "✅ Nạp ví thành công!\n\n"
        "💰 Số tiền: {amount}\n"
        "👛 Số dư mới: {balance}\n"
        "📋 Mã đơn: {order_code}"
    )
    msg = tpl.format(
        order_code=f"<b>{order['order_code']}</b>",
        amount=f"<b>{format_vnd(amount)}</b>",
        balance=f"<b>{format_vnd(new_balance)}</b>",
    )
    await _notify_user(bot, user_id, msg)


async def _refund_order(bot: Bot, order: dict, reason: str) -> None:
    """
    Hoàn tiền đơn hàng — chỉ refund nếu chưa refund trước đó.
    Kiểm tra is_refunded == 0 để chống hoàn 2 lần.
    """
    order_fresh = await get_order_by_id(order["id"])
    if not order_fresh or order_fresh["is_refunded"] == 1:
        logger.warning("Order %s already refunded, skipping", order["order_code"])
        return

    amount = order["amount"]
    user_id = order["user_id"]

    # Cộng tiền vào ví
    new_balance = await add_balance(
        user_id=user_id,
        amount=amount,
        tx_type="refund",
        reference_id=order["order_code"],
        description=f"Hoàn tiền - {reason}",
    )

    # Đánh dấu refunded
    await mark_refunded(order["id"], reason)

    await add_log(
        f"Refund {format_vnd(amount)} for order {order['order_code']}: {reason}",
        level="warning", module="poller",
    )

    # Thông báo user
    await _notify_user(
        bot, user_id,
        f"↩️ <b>Hoàn tiền đơn {order['order_code']}</b>\n\n"
        f"💰 Số tiền hoàn: <b>{format_vnd(amount)}</b>\n"
        f"👛 Số dư mới: <b>{format_vnd(new_balance)}</b>\n"
        f"📝 Lý do: {reason}"
    )

    # Thông báo admin
    await _notify_admins(
        bot,
        f"↩️ Refund order <b>{order['order_code']}</b>\n"
        f"Amount: {format_vnd(amount)}\n"
        f"Reason: {reason}"
    )


async def _expire_old_orders(bot: Bot) -> None:
    """Expire đơn QR quá hạn."""
    expire_minutes = await get_setting_int(
        "order_expire_min", env_settings.order_expire_minutes
    )

    pending_orders = await get_pending_qr_orders()
    now = datetime.utcnow()

    for order in pending_orders:
        created_str = order.get("created_at", "")
        if not created_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_str)
        except ValueError:
            continue

        if now - created_at > timedelta(minutes=expire_minutes):
            await update_order_status(
                order["id"], "expired",
                expired_at=now.isoformat(),
            )
            await add_log(
                f"Order {order['order_code']} expired after {expire_minutes}min",
                module="poller",
            )
            # Thông báo user
            await _notify_user(
                bot, order["user_id"],
                f"⌛ Đơn <b>{order['order_code']}</b> đã hết hạn.\n"
                f"Vui lòng tạo đơn mới nếu cần."
            )


async def _notify_user(bot: Bot, user_id: int, text: str) -> None:
    """Gửi tin nhắn cho user qua Telegram (bọc try/except)."""
    from db.queries.users import get_user_by_id
    user = await get_user_by_id(user_id)
    if not user:
        return
    try:
        await bot.send_message(
            chat_id=user["telegram_id"],
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Cannot notify user %d: %s", user_id, e)


async def _notify_admins(bot: Bot, text: str) -> None:
    """Gửi tin nhắn cho tất cả admin."""
    admin_ids_str = await get_setting("admin_telegram_ids") or env_settings.admin_telegram_ids
    if not admin_ids_str:
        return

    for tid_str in admin_ids_str.split(","):
        tid_str = tid_str.strip()
        if not tid_str.isdigit():
            continue
        try:
            await bot.send_message(
                chat_id=int(tid_str),
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Cannot notify admin %s: %s", tid_str, e)


# ── Wallet payment processing (không qua poller, xử lý ngay) ───────────────

async def process_wallet_payment(bot: Bot, order_id: int) -> bool:
    """
    Xử lý thanh toán bằng ví — gọi trực tiếp từ handler (không qua poller).
    Trừ ví → đổi status → process order.
    Returns True nếu thành công.
    """
    from db.queries.wallets import deduct_balance

    order = await get_order_by_id(order_id)
    if not order or order["status"] != "pending":
        return False

    try:
        # Trừ ví
        await deduct_balance(
            user_id=order["user_id"],
            amount=order["amount"],
            reference_id=order["order_code"],
            description=f"Thanh toán đơn {order['order_code']}",
        )
    except ValueError as e:
        # Không đủ tiền
        await _notify_user(bot, order["user_id"], f"❌ {e}")
        return False

    # Đánh dấu paid
    await update_order_status(
        order_id, "paid",
        paid_at=datetime.utcnow().isoformat(),
    )

    # Xử lý đơn ngay
    await _process_order(bot, order)
    return True
