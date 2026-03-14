"""
bot/handlers/start.py — /start command + welcome message + reply keyboard.
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.reply_kb import main_menu_kb
from db.queries.settings import get_setting

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: dict) -> None:
    """Xử lý /start — gửi lời chào + reply keyboard."""
    welcome = await get_setting("welcome_message") or "Chào mừng bạn đến với ShopBot!"
    bot_name = await get_setting("bot_name") or "ShopBot"
    bot_description = await get_setting("bot_description") or "Hệ thống bán Key API & ChatGPT tự động"

    name = db_user.get("full_name") or db_user.get("username") or "bạn"

    text = (
        f"👋 Xin chào <b>{name}</b>!\n\n"
        f"{welcome}\n\n"
        f"🤖 <b>{bot_name}</b> — {bot_description}\n\n"
        f"Sử dụng menu bên dưới để bắt đầu 👇"
    )

    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")
