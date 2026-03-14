"""
admin/routers/settings.py — Cài đặt MB/VietQR/Bot (tất cả key-value editable).
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.settings import get_settings_dict, set_setting

router = APIRouter(prefix="/settings", tags=["settings"])

_EDITABLE_KEYS = [
    "mb_api_url", "mb_api_key", "mb_username", "mb_password",
    "mb_account_no", "mb_account_name", "mb_bank_id",
    "poll_interval", "order_expire_min", "vietqr_template",
    "bot_name", "bot_description", "welcome_message", "support_url", "support_text",
    "pagination_size", "admin_telegram_ids", "admin_password",
]


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    all_settings = await get_settings_dict()
    templates = get_templates()
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "all_settings": all_settings},
    )


@router.post("/save")
async def settings_save(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    form = await request.form()
    for key in _EDITABLE_KEYS:
        value = form.get(key)
        if value is not None:
            await set_setting(key, value)

    return RedirectResponse("/settings?saved=1", status_code=303)
