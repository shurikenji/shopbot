"""
admin/deps.py — Dependencies cho admin routers.
get_current_admin: kiểm tra session login.
get_templates: Jinja2 templates instance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.utils.formatting import format_vnd, status_emoji, status_text_vi, format_time_vn
from bot.config import settings

_BASE_DIR = Path(__file__).resolve().parent
_templates: Optional[Jinja2Templates] = None


def get_templates() -> Jinja2Templates:
    """Lấy Jinja2 templates singleton."""
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
        # Thêm global functions cho templates
        _templates.env.globals["format_vnd"] = format_vnd
        _templates.env.globals["status_emoji"] = status_emoji
        _templates.env.globals["status_text_vi"] = status_text_vi
        _templates.env.filters["time_vn"] = format_time_vn
    return _templates


def require_admin(request: Request) -> dict:
    """
    Dependency: kiểm tra admin đã login.
    Redirect về đường dẫn cài đặt admin login nếu chưa.
    """
    admin = request.session.get("admin")
    if not admin:
        raise HTTPException(status_code=303, headers={"Location": settings.admin_login_path})
    return {"admin": True}


async def get_admin_or_redirect(request: Request) -> Optional[dict]:
    """Kiểm tra admin login, trả None nếu chưa."""
    return request.session.get("admin")
