"""
admin/deps.py - Shared helpers and dependencies for admin routers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from bot.config import settings
from bot.utils.formatting import (
    format_time_vn,
    format_vnd,
    status_emoji,
    status_text_vi,
)

_BASE_DIR = Path(__file__).resolve().parent
_templates: Optional[Jinja2Templates] = None


def get_templates() -> Jinja2Templates:
    """Return the singleton Jinja2 template environment for admin pages."""
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
        _templates.env.globals["format_vnd"] = format_vnd
        _templates.env.globals["status_emoji"] = status_emoji
        _templates.env.globals["status_text_vi"] = status_text_vi
        _templates.env.filters["time_vn"] = format_time_vn
    return _templates


def require_admin(request: Request) -> dict:
    """Ensure the current request has an authenticated admin session."""
    admin = request.session.get("admin")
    if not admin:
        raise HTTPException(
            status_code=303,
            headers={"Location": settings.admin_login_path},
        )
    return {"admin": True}


async def get_admin_or_redirect(request: Request) -> Optional[dict]:
    """Return the admin session payload when present."""
    return request.session.get("admin")


def protected_router(*, prefix: str = "", tags: list[str] | None = None) -> APIRouter:
    """Create an admin router protected by the session dependency."""
    return APIRouter(
        prefix=prefix,
        tags=tags,
        dependencies=[Depends(require_admin)],
    )
