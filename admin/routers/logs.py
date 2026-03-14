"""
admin/routers/logs.py — Xem + filter system logs.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.logs import get_logs, count_logs

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_class=HTMLResponse)
async def logs_page(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    page = int(request.query_params.get("page", 0))
    level = request.query_params.get("level", "")
    module = request.query_params.get("module", "")
    search = request.query_params.get("search", "")
    per_page = 30

    logs = await get_logs(
        offset=page * per_page, limit=per_page,
        level=level or None, module=module or None,
        search=search or None,
    )
    total = await count_logs(
        level=level or None, module=module or None,
        search=search or None,
    )
    total_pages = max(1, math.ceil(total / per_page))

    templates = get_templates()
    return templates.TemplateResponse(
        "logs.html",
        {"request": request, "logs": logs,
         "page": page, "total_pages": total_pages,
         "filter_level": level, "filter_module": module,
         "filter_search": search},
    )
