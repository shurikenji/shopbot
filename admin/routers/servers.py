"""
admin/routers/servers.py — CRUD API servers + fetch groups từ NewAPI.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.servers import (
    get_all_servers, get_server_by_id,
    create_server, update_server, delete_server,
)
from bot.services.newapi import get_groups

router = APIRouter(prefix="/servers", tags=["servers"])


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
async def servers_list(request: Request):
    r = _check(request)
    if r: return r
    servers = await get_all_servers()
    templates = get_templates()
    return templates.TemplateResponse(
        "servers.html", {"request": request, "servers": servers}
    )


@router.post("/add")
async def servers_add(request: Request):
    r = _check(request)
    if r: return r
    form = await request.form()
    await create_server(
        name=form["name"],
        base_url=form["base_url"],
        user_id_header=form["user_id_header"],
        access_token=form["access_token"],
        price_per_unit=int(form["price_per_unit"]),
        quota_per_unit=int(form["quota_per_unit"]),
        dollar_per_unit=float(form.get("dollar_per_unit", 10.0)),
        quota_multiple=float(form.get("quota_multiple", 1.0)),
        default_group=form.get("default_group", ""),
    )
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/edit", response_class=HTMLResponse)
async def servers_edit_page(request: Request, server_id: int):
    r = _check(request)
    if r: return r
    server = await get_server_by_id(server_id)
    if not server:
        return RedirectResponse("/servers", status_code=303)
    templates = get_templates()
    return templates.TemplateResponse(
        "servers.html",
        {"request": request, "servers": await get_all_servers(),
         "editing": server},
    )


@router.post("/{server_id}/edit")
async def servers_edit_submit(request: Request, server_id: int):
    r = _check(request)
    if r: return r
    form = await request.form()
    await update_server(
        server_id,
        name=form.get("name"),
        base_url=form.get("base_url"),
        user_id_header=form.get("user_id_header"),
        access_token=form.get("access_token"),
        price_per_unit=int(form["price_per_unit"]) if form.get("price_per_unit") else None,
        quota_per_unit=int(form["quota_per_unit"]) if form.get("quota_per_unit") else None,
        dollar_per_unit=float(form["dollar_per_unit"]) if form.get("dollar_per_unit") else None,
        quota_multiple=float(form["quota_multiple"]) if form.get("quota_multiple") else None,
        default_group=form.get("default_group"),
        is_active=1 if form.get("is_active") else 0,
    )
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/delete")
async def servers_delete(request: Request, server_id: int):
    r = _check(request)
    if r: return r
    await delete_server(server_id)
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/groups", response_class=HTMLResponse)
async def servers_groups(request: Request, server_id: int):
    """Fetch groups từ NewAPI server."""
    r = _check(request)
    if r: return r
    server = await get_server_by_id(server_id)
    if not server:
        return RedirectResponse("/servers", status_code=303)

    groups = await get_groups(server)
    # Render simple response
    templates = get_templates()
    servers = await get_all_servers()
    return templates.TemplateResponse(
        "servers.html",
        {"request": request, "servers": servers,
         "groups_server": server, "groups_data": groups},
    )


@router.get("/{server_id}/api/groups")
async def api_servers_groups(request: Request, server_id: int):
    """Fetch groups từ NewAPI server (JSON response)."""
    r = _check(request)
    if r:
        return {"success": False, "message": "Unauthorized"}
    
    server = await get_server_by_id(server_id)
    if not server:
        return {"success": False, "message": "Server not found"}

    groups = await get_groups(server)
    return {"success": True, "data": groups}
