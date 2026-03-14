"""
bot/keyboards/reply_kb.py — Reply keyboard chính (6 nút, 2 cột).
Luôn hiển thị dưới chat khi user tương tác.
"""
from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Reply keyboard chính — 6 nút chia 2 cột."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛒 Sản phẩm"),
                KeyboardButton(text="👛 Ví"),
            ],
            [
                KeyboardButton(text="📋 Đơn hàng"),
                KeyboardButton(text="🔎 Tìm đơn"),
            ],
            [
                KeyboardButton(text="👤 Tài khoản"),
                KeyboardButton(text="🆘 Hỗ trợ"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
