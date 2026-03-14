"""
admin/routers/dashboard.py — Dashboard thống kê tổng quan.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates, require_admin
from bot.config import settings
from db.queries.orders import get_order_stats
from db.queries.users import count_users
from db.queries.servers import get_all_servers

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    stats = await get_order_stats()
    stats["total_users"] = await count_users()
    servers = await get_all_servers()
    stats["servers"] = servers

    templates = get_templates()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats},
    )
