"""
admin/routers/orders.py — Xem/xử lý đơn hàng (list + detail + manual complete).
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.orders import (
    get_all_orders, count_all_orders, get_order_by_id,
    update_order_status, cancel_order,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
async def orders_list(request: Request):
    r = _check(request)
    if r: return r

    page = int(request.query_params.get("page", 0))
    status = request.query_params.get("status", "")
    search = request.query_params.get("search", "")
    per_page = 20

    orders = await get_all_orders(
        offset=page * per_page, limit=per_page,
        status=status or None, search=search or None,
    )
    total = await count_all_orders(
        status=status or None, search=search or None,
    )
    total_pages = max(1, math.ceil(total / per_page))

    templates = get_templates()
    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "orders": orders,
         "page": page, "total_pages": total_pages,
         "filter_status": status, "filter_search": search},
    )


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_detail(request: Request, order_id: int):
    r = _check(request)
    if r: return r
    order = await get_order_by_id(order_id)
    if not order:
        return RedirectResponse("/orders", status_code=303)
    templates = get_templates()
    return templates.TemplateResponse(
        "order_detail.html", {"request": request, "order": order}
    )


@router.post("/{order_id}/complete")
async def order_complete(request: Request, order_id: int):
    """Hoàn thành đơn service_upgrade."""
    r = _check(request)
    if r: return r

    order = await get_order_by_id(order_id)
    if not order:
        return RedirectResponse("/orders", status_code=303)

    await update_order_status(
        order_id, "completed"
    )

    # Thông báo user qua bot
    try:
        from bot.config import settings
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from db.queries.users import get_user_by_id

        if settings.bot_token:
            bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            user = await get_user_by_id(order["user_id"])
            if user:
                await bot.send_message(
                    chat_id=user["telegram_id"],
                    text=(
                        f"✅ Đơn dịch vụ <b>{order['order_code']}</b> của bạn đã được Admin xử lý hoàn tất!\n\n"
                        f"🎉 Cảm ơn bạn đã sử dụng dịch vụ."
                    ),
                )
            await bot.session.close()
    except Exception:
        pass

    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.get("/{order_id}/cancel")
async def order_cancel(request: Request, order_id: int):
    r = _check(request)
    if r: return r
    await cancel_order(order_id)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.get("/{order_id}/refund")
async def order_refund(request: Request, order_id: int):
    """Hoàn tiền cho đơn hàng đã thanh toán."""
    r = _check(request)
    if r: return r

    order = await get_order_by_id(order_id)
    if not order:
        return RedirectResponse("/orders", status_code=303)

    if order["status"] not in ("paid", "processing", "completed"):
        # Chỉ hoàn tiền các đơn đã thanh toán hoặc hoàn thành
        return RedirectResponse(f"/orders/{order_id}", status_code=303)

    if order["product_type"] == "wallet_topup":
        # Ngăn chặn hoàn tiền đối với giao dịch nạp ví thực
        return RedirectResponse(f"/orders/{order_id}", status_code=303)

    from db.queries.wallets import add_balance
    from db.queries.logs import add_log
    from bot.utils.formatting import format_vnd

    # 1. Hoàn tiền
    await add_balance(order["user_id"], order["amount"], f"Hoàn tiền đơn {order['order_code']}")
    
    # 2. Đổi trạng thái đơn
    await update_order_status(
        order_id, "refunded",
        refund_reason="Admin hoàn tiền"
    )

    # 3. Ghi log hệ thống
    await add_log(
        f"Admin hoàn tiền đơn {order['order_code']}, số tiền {format_vnd(order['amount'])}",
        module="admin"
    )

    # 4. Gửi thông báo Telegram cho user
    try:
        from bot.config import settings
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from db.queries.users import get_user_by_id

        if settings.bot_token:
            bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            user = await get_user_by_id(order["user_id"])
            if user:
                await bot.send_message(
                    chat_id=user["telegram_id"],
                    text=(
                        f"↩️ Đơn <b>{order['order_code']}</b> đã bị huỷ.\n\n"
                        f"💳 Bạn được hoàn <b>{format_vnd(order['amount'])}</b> vào số dư ví."
                    ),
                )
            await bot.session.close()
    except Exception as e:
        print(f"Error sending refund notif: {e}")

    return RedirectResponse(f"/orders/{order_id}", status_code=303)
