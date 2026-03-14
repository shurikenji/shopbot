"""
admin/routers/broadcast.py — Gửi broadcast message đến tất cả users.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.users import get_all_user_telegram_ids, count_users
from db.queries.logs import add_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcast", tags=["broadcast"])


@router.get("", response_class=HTMLResponse)
async def broadcast_page(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    total_users = await count_users()
    templates = get_templates()
    return templates.TemplateResponse(
        "broadcast.html",
        {"request": request, "total_users": total_users},
    )


@router.post("/send")
async def broadcast_send(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    form = await request.form()
    message = form.get("message", "")

    if not message.strip():
        return RedirectResponse("/broadcast", status_code=303)

    # Gửi broadcast qua bot
    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        if not settings.bot_token:
            await add_log("Broadcast failed: BOT_TOKEN not set", level="error", module="broadcast")
            return RedirectResponse("/broadcast", status_code=303)

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        telegram_ids = await get_all_user_telegram_ids()
        sent = 0
        failed = 0

        for tid in telegram_ids:
            try:
                await bot.send_message(chat_id=tid, text=message)
                sent += 1
            except Exception as e:
                logger.warning("Broadcast to %d failed: %s", tid, e)
                failed += 1
            # Rate limiting — tối đa 30 msg/s theo Telegram API
            await asyncio.sleep(0.05)

        await bot.session.close()
        await add_log(
            f"Broadcast sent: {sent} success, {failed} failed",
            module="broadcast",
        )

    except Exception as e:
        logger.error("Broadcast error: %s", e)
        await add_log(f"Broadcast error: {e}", level="error", module="broadcast")

    return RedirectResponse("/broadcast", status_code=303)
