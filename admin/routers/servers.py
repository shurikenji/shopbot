"""
admin/routers/servers.py — CRUD API servers + fetch groups.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from bot.services.api_clients import get_api_client
from bot.services.ai_translator import get_translator
from db.queries.servers import (
    get_all_servers,
    get_server_by_id,
    create_server,
    update_server,
    delete_server,
)

router = APIRouter(prefix="/servers", tags=["servers"])


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
async def servers_list(request: Request):
    r = _check(request)
    if r:
        return r
    servers = await get_all_servers()
    templates = get_templates()
    return templates.TemplateResponse(
        "servers.html",
        {
            "request": request,
            "servers": servers,
            "api_types": [
                {"value": "newapi", "label": "NewAPI"},
                {"value": "rixapi", "label": "RixAPI"},
                {"value": "other", "label": "Other (Custom)"},
            ],
            "auth_types": [
                {"value": "header", "label": "Header + Bearer"},
                {"value": "bearer_only", "label": "Bearer Only"},
                {"value": "cookie", "label": "Cookie Auth"},
                {"value": "none", "label": "No Auth"},
            ],
        },
    )


@router.post("/add")
async def servers_add(request: Request):
    r = _check(request)
    if r:
        return r
    form = await request.form()
    
    # Get auth values
    api_type = form.get("api_type", "newapi")
    auth_type = form.get("auth_type", "header")
    
    # Get auth fields based on auth_type
    auth_user_header = form.get("auth_user_header", "")
    auth_user_value = form.get("auth_user_value", "")
    auth_token = form.get("auth_token", "")
    auth_cookie = form.get("auth_cookie", "")
    
    # Legacy fields fallback
    if not auth_user_header:
        auth_user_header = form.get("user_id_header", "new-api-user")
    if not auth_user_value:
        auth_user_value = form.get("user_id_header", "")
    if not auth_token:
        auth_token = form.get("access_token", "")
    
    # Custom headers (JSON)
    custom_headers = form.get("custom_headers", "")
    
    await create_server(
        name=form["name"],
        base_url=form["base_url"],
        user_id_header=auth_user_header,
        access_token=auth_token,
        price_per_unit=int(form["price_per_unit"]),
        quota_per_unit=int(form["quota_per_unit"]),
        dollar_per_unit=float(form.get("dollar_per_unit", 10.0)),
        quota_multiple=float(form.get("quota_multiple", 1.0)),
        default_group=form.get("default_group", ""),
        # New fields
        api_type=api_type,
        supports_multi_group=1 if form.get("supports_multi_group") else 0,
        manual_groups=form.get("manual_groups", ""),
        auth_type=auth_type,
        auth_user_header=auth_user_header,
        auth_user_value=auth_user_value,
        auth_token=auth_token,
        auth_cookie=auth_cookie,
        custom_headers=custom_headers,
        groups_endpoint=form.get("groups_endpoint", ""),
    )
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/edit", response_class=HTMLResponse)
async def servers_edit_page(request: Request, server_id: int):
    r = _check(request)
    if r:
        return r
    server = await get_server_by_id(server_id)
    if not server:
        return RedirectResponse("/servers", status_code=303)
    templates = get_templates()
    
    # Ensure defaults for new fields
    server.setdefault("api_type", "newapi")
    server.setdefault("supports_multi_group", 0)
    server.setdefault("auth_type", "header")
    server.setdefault("auth_user_header", "new-api-user")
    server.setdefault("manual_groups", "")
    server.setdefault("custom_headers", "")
    server.setdefault("groups_endpoint", "")
    
    return templates.TemplateResponse(
        "servers.html",
        {
            "request": request,
            "servers": await get_all_servers(),
            "editing": server,
            "api_types": [
                {"value": "newapi", "label": "NewAPI"},
                {"value": "rixapi", "label": "RixAPI"},
                {"value": "other", "label": "Other (Custom)"},
            ],
            "auth_types": [
                {"value": "header", "label": "Header + Bearer"},
                {"value": "bearer_only", "label": "Bearer Only"},
                {"value": "cookie", "label": "Cookie Auth"},
                {"value": "none", "label": "No Auth"},
            ],
        },
    )


@router.post("/{server_id}/edit")
async def servers_edit_submit(request: Request, server_id: int):
    r = _check(request)
    if r:
        return r
    form = await request.form()
    
    # Get auth values
    api_type = form.get("api_type", "newapi")
    auth_type = form.get("auth_type", "header")
    
    # Get auth fields based on auth_type
    auth_user_header = form.get("auth_user_header", "")
    auth_user_value = form.get("auth_user_value", "")
    auth_token = form.get("auth_token", "")
    auth_cookie = form.get("auth_cookie", "")
    
    # Legacy fields fallback
    if not auth_user_header:
        auth_user_header = form.get("user_id_header", "new-api-user")
    if not auth_user_value:
        auth_user_value = form.get("user_id_header", "")
    if not auth_token:
        auth_token = form.get("access_token", "")
    
    # Custom headers (JSON)
    custom_headers = form.get("custom_headers", "")
    
    await update_server(
        server_id,
        name=form.get("name"),
        base_url=form.get("base_url"),
        user_id_header=auth_user_header,
        access_token=auth_token,
        price_per_unit=int(form["price_per_unit"]) if form.get("price_per_unit") else None,
        quota_per_unit=int(form["quota_per_unit"]) if form.get("quota_per_unit") else None,
        dollar_per_unit=float(form["dollar_per_unit"]) if form.get("dollar_per_unit") else None,
        quota_multiple=float(form["quota_multiple"]) if form.get("quota_multiple") else None,
        default_group=form.get("default_group"),
        is_active=1 if form.get("is_active") else 0,
        # New fields
        api_type=api_type,
        supports_multi_group=1 if form.get("supports_multi_group") else 0,
        manual_groups=form.get("manual_groups"),
        auth_type=auth_type,
        auth_user_header=auth_user_header,
        auth_user_value=auth_user_value,
        auth_token=auth_token,
        auth_cookie=auth_cookie,
        custom_headers=custom_headers,
        groups_endpoint=form.get("groups_endpoint"),
    )
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/delete")
async def servers_delete(request: Request, server_id: int):
    r = _check(request)
    if r:
        return r
    await delete_server(server_id)
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/groups", response_class=HTMLResponse)
async def servers_groups(request: Request, server_id: int):
    """Fetch groups từ server."""
    r = _check(request)
    if r:
        return r
    server = await get_server_by_id(server_id)
    if not server:
        return RedirectResponse("/servers", status_code=303)

    # Use API client factory
    client = get_api_client(server)
    groups = await client.get_groups(server)
    
    # Translate with AI if enabled
    translator = await get_translator()
    if translator.is_configured:
        groups = await translator.translate_groups(groups, server.get("api_type", "newapi"))
    
    # Parse groups for display
    parsed_groups = []
    for g in groups:
        parsed_groups.append({
            "name": g.get("name", ""),
            "label_vi": g.get("label_vi") or g.get("name_vi") or g.get("name", ""),
            "ratio": g.get("ratio", 1.0),
            "desc": g.get("desc", ""),
            "category": g.get("category", "Other"),
        })
    
    templates = get_templates()
    servers = await get_all_servers()
    return templates.TemplateResponse(
        "servers.html",
        {
            "request": request,
            "servers": servers,
            "groups_server": server,
            "groups_data": parsed_groups,
            "supports_multi_group": server.get("supports_multi_group", 0),
            "api_types": [
                {"value": "newapi", "label": "NewAPI"},
                {"value": "rixapi", "label": "RixAPI"},
                {"value": "other", "label": "Other (Custom)"},
            ],
            "auth_types": [
                {"value": "header", "label": "Header + Bearer"},
                {"value": "bearer_only", "label": "Bearer Only"},
                {"value": "cookie", "label": "Cookie Auth"},
                {"value": "none", "label": "No Auth"},
            ],
        },
    )


@router.get("/{server_id}/api/groups")
async def api_servers_groups(request: Request, server_id: int):
    """Fetch groups từ server (JSON response)."""
    r = _check(request)
    if r:
        return JSONResponse({"success": False, "message": "Unauthorized"})
    
    server = await get_server_by_id(server_id)
    if not server:
        return JSONResponse({"success": False, "message": "Server not found"})

    # Check for manual groups first
    manual_groups = server.get("manual_groups", "")
    if manual_groups:
        # Parse manual groups
        groups = []
        for name in manual_groups.split(","):
            name = name.strip()
            if name:
                groups.append({
                    "name": name,
                    "ratio": 1.0,
                    "desc": "",
                    "category": "Other",
                })
        return JSONResponse({"success": True, "data": groups})

    # Use API client factory
    client = get_api_client(server)
    groups = await client.get_groups(server)
    
    # Translate with AI if enabled
    translator = await get_translator()
    if translator.is_configured:
        groups = await translator.translate_groups(groups, server.get("api_type", "newapi"))
    
    return JSONResponse({"success": True, "data": groups})
