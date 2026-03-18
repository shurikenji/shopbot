"""
bot/keyboards/inline_kb.py — Tất cả inline keyboard builders.
Mỗi hàm trả về InlineKeyboardMarkup sẵn sàng gửi.
"""
from __future__ import annotations

import math
from typing import Sequence

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callback_data.factories import (
    CategoryPageCB,
    CategorySelectCB,
    KeyActionCB,
    ServerSelectCB,
    ProductPageCB,
    ProductSelectCB,
    PaymentMethodCB,
    OrderCancelCB,
    MyKeySelectCB,
    MyKeyInputCB,
    CustomAmountCB,
    WalletActionCB,
    WalletTopupAmountCB,
    OrderListPageCB,
    OrderDetailCB,
    BackCB,
)
from bot.utils.formatting import format_vnd


# ── Helpers ─────────────────────────────────────────────────────────────────

def _paginate(items: Sequence, page: int, per_page: int) -> tuple[list, int]:
    """Trả về (items trang hiện tại, tổng số trang)."""
    total_pages = max(1, math.ceil(len(items) / per_page))
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return list(items[start : start + per_page]), total_pages


# ── Danh mục ────────────────────────────────────────────────────────────────

def categories_kb(
    categories: Sequence[dict],
    page: int = 0,
    per_page: int = 6,
) -> InlineKeyboardMarkup:
    """Inline keyboard danh mục có phân trang."""
    page_items, total_pages = _paginate(categories, page, per_page)

    builder = InlineKeyboardBuilder()
    for cat in page_items:
        icon = cat.get("icon", "📦")
        name = cat.get("name", "")
        builder.button(
            text=f"{icon} {name}",
            callback_data=CategorySelectCB(id=cat["id"]),
        )
    builder.adjust(1)  # Đổi thành 1 cột để hiển thị tên dài tốt hơn

    # Pagination row
    if total_pages > 1:
        nav_buttons: list[InlineKeyboardButton] = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Trước",
                    callback_data=CategoryPageCB(page=page - 1).pack(),
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop",
            )
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Sau ➡️",
                    callback_data=CategoryPageCB(page=page + 1).pack(),
                )
            )
        builder.row(*nav_buttons)

    return builder.as_markup()


# ── Key API sub-menu ────────────────────────────────────────────────────────

def key_action_kb(cat_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard: Mua key mới / Nạp key cũ."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔑 Mua key mới",
        callback_data=KeyActionCB(cat_id=cat_id, action="new"),
    )
    builder.button(
        text="💳 Nạp key cũ",
        callback_data=KeyActionCB(cat_id=cat_id, action="topup"),
    )
    builder.button(
        text="⬅️ Quay lại",
        callback_data=BackCB(target="cat"),
    )
    builder.adjust(2, 1)
    return builder.as_markup()


# ── Server selection ────────────────────────────────────────────────────────

def servers_kb(
    servers: Sequence[dict],
    action: str,
) -> InlineKeyboardMarkup:
    """Inline keyboard chọn server."""
    builder = InlineKeyboardBuilder()
    for srv in servers:
        dollar_per_unit = srv.get("dollar_per_unit", 10.0)
        if dollar_per_unit <= 0: dollar_per_unit = 10.0
        price_per_dollar = int(srv["price_per_unit"] / dollar_per_unit)
        price = format_vnd(price_per_dollar)
        
        builder.button(
            text=f"🖥 {srv['name']} ({price}/$)",
            callback_data=ServerSelectCB(action=action, server_id=srv["id"]),
        )
    builder.button(
        text="⬅️ Quay lại",
        callback_data=BackCB(target="cat"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ── Products (gói) ──────────────────────────────────────────────────────────

def products_kb(
    products: Sequence[dict],
    cat_id: int,
    srv_id: int,
    ptype: str,
    page: int = 0,
    per_page: int = 6,
    action: str = "new",
) -> InlineKeyboardMarkup:
    """Inline keyboard danh sách sản phẩm/gói có phân trang."""
    page_items, total_pages = _paginate(products, page, per_page)

    builder = InlineKeyboardBuilder()
    for prod in page_items:
        price = format_vnd(prod["price_vnd"])
        stock_text = ""
        if prod.get("stock", -1) != -1:
            stock_text = f" [Còn {prod['stock']}]"
            
        builder.button(
            text=f"{prod['name']} — {price}{stock_text}",
            callback_data=ProductSelectCB(product_id=prod["id"]),
        )
    builder.adjust(1)

    # Nút nhập số $ tùy chọn (chỉ cho key_new / key_topup)
    if ptype in ("key_new", "key_topup") and srv_id > 0:
        builder.row(
            InlineKeyboardButton(
                text="✏️ Nhập số $ tùy chọn",
                callback_data=CustomAmountCB(
                    action=action, server_id=srv_id
                ).pack(),
            )
        )

    # Pagination
    if total_pages > 1:
        nav_buttons: list[InlineKeyboardButton] = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Trước",
                    callback_data=ProductPageCB(
                        cat_id=cat_id, srv_id=srv_id, ptype=ptype, page=page - 1
                    ).pack(),
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop",
            )
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Sau ➡️",
                    callback_data=ProductPageCB(
                        cat_id=cat_id, srv_id=srv_id, ptype=ptype, page=page + 1
                    ).pack(),
                )
            )
        builder.row(*nav_buttons)

    # Back
    back_target = "srv" if srv_id > 0 else "cat"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Quay lại",
            callback_data=BackCB(target=back_target).pack(),
        )
    )
    return builder.as_markup()


# ── Payment method ──────────────────────────────────────────────────────────

def payment_method_kb(order_id: int, show_qr: bool = True) -> InlineKeyboardMarkup:
    """Inline keyboard chọn phương thức thanh toán."""
    builder = InlineKeyboardBuilder()
    if show_qr:
        builder.button(
            text="🏦 Chuyển khoản QR",
            callback_data=PaymentMethodCB(order_id=order_id, method="qr"),
        )
    builder.button(
        text="👛 Thanh toán bằng ví",
        callback_data=PaymentMethodCB(order_id=order_id, method="wallet"),
    )
    builder.button(
        text="❌ Hủy đơn",
        callback_data=OrderCancelCB(order_id=order_id),
    )
    if show_qr:
        builder.adjust(2, 1)
    else:
        builder.adjust(1, 1)
    return builder.as_markup()


# ── My keys (chọn key để topup) ────────────────────────────────────────────

def my_keys_kb(
    keys: Sequence[dict],
    server_id: int,
) -> InlineKeyboardMarkup:
    """Inline keyboard chọn key hiện có hoặc nhập key mới."""
    builder = InlineKeyboardBuilder()
    for key_row in keys:
        label = key_row.get("label") or key_row.get("api_key", "")
        # Mask key cho an toàn
        if len(label) > 20:
            label = f"{label[:8]}...{label[-4:]}"
        builder.button(
            text=f"🔑 {label}",
            callback_data=MyKeySelectCB(key_id=key_row["id"]),
        )
    builder.button(
        text="✏️ Nhập key mới",
        callback_data=MyKeyInputCB(server_id=server_id),
    )
    builder.button(
        text="⬅️ Quay lại",
        callback_data=BackCB(target="srv"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ── Wallet ──────────────────────────────────────────────────────────────────

def wallet_menu_kb() -> InlineKeyboardMarkup:
    """Inline keyboard ví: nạp tiền / lịch sử."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💰 Nạp tiền",
        callback_data=WalletActionCB(action="topup"),
    )
    builder.button(
        text="📜 Lịch sử giao dịch",
        callback_data=WalletActionCB(action="history"),
    )
    builder.adjust(2)
    return builder.as_markup()


def wallet_topup_amounts_kb() -> InlineKeyboardMarkup:
    """Inline keyboard chọn số tiền nạp ví (preset + custom)."""
    presets = [50_000, 100_000, 200_000, 500_000, 1_000_000]

    builder = InlineKeyboardBuilder()
    for amt in presets:
        builder.button(
            text=format_vnd(amt),
            callback_data=WalletTopupAmountCB(amount=amt),
        )
    builder.button(
        text="✏️ Nhập số khác",
        callback_data=WalletTopupAmountCB(amount=0),
    )
    builder.button(
        text="⬅️ Quay lại",
        callback_data=BackCB(target="wallet"),
    )
    builder.adjust(3, 2, 1, 1)
    return builder.as_markup()


# ── Order list ──────────────────────────────────────────────────────────────

def orders_list_kb(
    orders: Sequence[dict],
    page: int = 0,
    per_page: int = 6,
) -> InlineKeyboardMarkup:
    """Inline keyboard danh sách đơn hàng có phân trang."""
    page_items, total_pages = _paginate(orders, page, per_page)

    builder = InlineKeyboardBuilder()
    for order in page_items:
        code = order.get("order_code", "???")
        status = order.get("status", "pending")
        from bot.utils.formatting import status_emoji
        emoji = status_emoji(status)
        builder.button(
            text=f"{emoji} {code}",
            callback_data=OrderDetailCB(order_id=order["id"]),
        )
    builder.adjust(2)

    # Pagination
    if total_pages > 1:
        nav_buttons: list[InlineKeyboardButton] = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Trước",
                    callback_data=OrderListPageCB(page=page - 1).pack(),
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop",
            )
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Sau ➡️",
                    callback_data=OrderListPageCB(page=page + 1).pack(),
                )
            )
        builder.row(*nav_buttons)

    return builder.as_markup()


# ── Confirm / Cancel generic ────────────────────────────────────────────────

def order_cancel_kb(order_id: int) -> InlineKeyboardMarkup:
    """Nút hủy đơn."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="❌ Hủy đơn hàng",
        callback_data=OrderCancelCB(order_id=order_id),
    )
    return builder.as_markup()


def order_detail_kb(
    order_id: int,
    can_cancel: bool = False,
) -> InlineKeyboardMarkup:
    """Nút cho màn chi tiết đơn hàng."""
    builder = InlineKeyboardBuilder()
    if can_cancel:
        builder.button(
            text="❌ Hủy đơn hàng",
            callback_data=OrderCancelCB(order_id=order_id),
        )
    builder.button(text="⬅️ Quay lại", callback_data=BackCB(target="orders_back"))
    builder.adjust(1)
    return builder.as_markup()


def back_only_kb(
    target: str,
    text: str = "⬅️ Quay lại",
) -> InlineKeyboardMarkup:
    """Inline keyboard chỉ gồm 1 nút quay lại."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=BackCB(target=target))
    return builder.as_markup()
