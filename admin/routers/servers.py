"""
admin/routers/servers.py - API server CRUD and group inspection routes.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from admin.deps import get_templates, protected_router
from bot.services.ai_translator import get_translator
from bot.services.api_clients import get_api_client
from db.queries.servers import (
    create_server,
    delete_server,
    get_all_servers,
    get_server_by_id,
    update_server,
)

router = protected_router(prefix="/servers", tags=["servers"])

_API_TYPES = [
    {"value": "newapi", "label": "NewAPI"},
    {"value": "rixapi", "label": "RixAPI"},
    {"value": "other", "label": "Other (Custom)"},
]

_AUTH_TYPES = [
    {"value": "header", "label": "Header + Bearer"},
    {"value": "bearer_only", "label": "Bearer Only"},
    {"value": "cookie", "label": "Cookie Auth"},
    {"value": "none", "label": "No Auth"},
]


def _clean_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _server_page_context(*, request: Request, servers: list[dict], **extra: object) -> dict[str, object]:
    return {
        "request": request,
        "servers": servers,
        "api_types": _API_TYPES,
        "auth_types": _AUTH_TYPES,
        **extra,
    }


async def _load_servers_for_page() -> list[dict]:
    servers = await get_all_servers()
    for server in servers:
        if _clean_str(server.get("api_type", "newapi"), "newapi").lower() == "rixapi":
            server["supports_multi_group"] = 1
    return servers


def _build_manual_group_rows(manual_groups: str) -> list[dict]:
    return [
        {
            "name": name.strip(),
            "label_en": name.strip(),
            "ratio": 1.0,
            "desc": "",
            "category": "Other",
        }
        for name in manual_groups.split(",")
        if name.strip()
    ]


def _get_server_form_payload(form) -> dict:
    api_type = _clean_str(form.get("api_type", "newapi"), "newapi").lower()
    legacy_user_id = _clean_str(form.get("auth_user_value") or form.get("user_id_header"))
    legacy_token = _clean_str(form.get("auth_token") or form.get("access_token"))

    payload = {
        "name": _clean_str(form.get("name")),
        "base_url": _clean_str(form.get("base_url")),
        "price_per_unit": int(form["price_per_unit"]) if form.get("price_per_unit") else None,
        "quota_per_unit": int(form["quota_per_unit"]) if form.get("quota_per_unit") else None,
        "dollar_per_unit": float(form.get("dollar_per_unit", 10.0)),
        "quota_multiple": float(form.get("quota_multiple", 1.0)),
        "default_group": _clean_str(form.get("default_group")),
        "api_type": api_type,
    }

    if api_type == "newapi":
        payload.update(
            {
                "user_id_header": legacy_user_id,
                "access_token": legacy_token,
                "supports_multi_group": 1 if form.get("supports_multi_group") else 0,
                "manual_groups": _clean_str(form.get("manual_groups")),
                "auth_type": "header",
                "auth_user_header": "new-api-user",
                "auth_user_value": legacy_user_id,
                "auth_token": legacy_token,
                "auth_cookie": "",
                "custom_headers": "",
                "groups_endpoint": "",
            }
        )
        return payload

    if api_type == "rixapi":
        payload.update(
            {
                "user_id_header": legacy_user_id,
                "access_token": legacy_token,
                "supports_multi_group": 1,
                "manual_groups": _clean_str(form.get("manual_groups")),
                "auth_type": "header",
                "auth_user_header": "rix-api-user",
                "auth_user_value": legacy_user_id,
                "auth_token": legacy_token,
                "auth_cookie": "",
                "custom_headers": "",
                "groups_endpoint": "",
            }
        )
        return payload

    auth_type = _clean_str(form.get("auth_type", "header"), "header")
    auth_user_header = _clean_str(form.get("auth_user_header"), "new-api-user")
    auth_user_value = _clean_str(form.get("auth_user_value"))
    auth_token = _clean_str(form.get("auth_token"))
    auth_cookie = _clean_str(form.get("auth_cookie"))

    payload.update(
        {
            "user_id_header": auth_user_value,
            "access_token": auth_token,
            "supports_multi_group": 1 if form.get("supports_multi_group") else 0,
            "manual_groups": _clean_str(form.get("manual_groups")),
            "auth_type": auth_type,
            "auth_user_header": auth_user_header,
            "auth_user_value": auth_user_value,
            "auth_token": auth_token,
            "auth_cookie": auth_cookie,
            "custom_headers": _clean_str(form.get("custom_headers")),
            "groups_endpoint": _clean_str(form.get("groups_endpoint")),
        }
    )
    return payload


def _normalize_server_for_form(server: dict) -> dict:
    api_type = _clean_str(server.get("api_type", "newapi"), "newapi").lower()
    legacy_user_id = _clean_str(server.get("auth_user_value") or server.get("user_id_header"))
    token = _clean_str(server.get("auth_token") or server.get("access_token"))

    server["api_type"] = api_type
    server["supports_multi_group"] = server.get("supports_multi_group", 0)
    server["manual_groups"] = server.get("manual_groups", "") or ""
    server["custom_headers"] = server.get("custom_headers", "") or ""
    server["groups_endpoint"] = server.get("groups_endpoint", "") or ""
    server["auth_cookie"] = server.get("auth_cookie", "") or ""
    server["auth_token"] = token
    server["auth_user_value"] = legacy_user_id

    if api_type == "rixapi":
        server["supports_multi_group"] = 1
        if not server["manual_groups"] and "," in server.get("default_group", ""):
            server["manual_groups"] = server.get("default_group", "")
        server["auth_type"] = "header"
        server["auth_user_header"] = "rix-api-user"
    elif api_type == "newapi":
        if not server["manual_groups"] and "," in server.get("default_group", ""):
            server["manual_groups"] = server.get("default_group", "")
        server["auth_type"] = "header"
        server["auth_user_header"] = "new-api-user"
    else:
        server["auth_type"] = server.get("auth_type", "header") or "header"
        server["auth_user_header"] = (
            server.get("auth_user_header", "new-api-user") or "new-api-user"
        )

    return server


async def _load_and_translate_groups(server: dict) -> list[dict]:
    client = get_api_client(server)
    groups = await client.get_groups(server)

    translator = await get_translator()
    if translator.is_configured:
        groups = await translator.translate_groups(groups, server.get("api_type", "newapi"))

    parsed_groups = []
    for group in groups:
        parsed_groups.append(
            {
                "name": group.get("name", ""),
                "label_en": group.get("label_en") or group.get("name_en") or group.get("name", ""),
                "label_vi": group.get("label_vi") or group.get("name_vi") or group.get("name", ""),
                "ratio": group.get("ratio", 1.0),
                "desc": group.get("desc_en") or group.get("desc", ""),
                "category": group.get("category", "Other"),
            }
        )
    return parsed_groups


@router.get("", response_class=HTMLResponse)
async def servers_list(request: Request):
    templates = get_templates()
    return templates.TemplateResponse(
        "servers.html",
        _server_page_context(request=request, servers=await _load_servers_for_page()),
    )


@router.post("/add")
async def servers_add(request: Request):
    form = await request.form()
    await create_server(**_get_server_form_payload(form))
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/edit", response_class=HTMLResponse)
async def servers_edit_page(request: Request, server_id: int):
    server = await get_server_by_id(server_id)
    if not server:
        return RedirectResponse("/servers", status_code=303)

    templates = get_templates()
    return templates.TemplateResponse(
        "servers.html",
        _server_page_context(
            request=request,
            servers=await _load_servers_for_page(),
            editing=_normalize_server_for_form(server),
        ),
    )


@router.post("/{server_id}/edit")
async def servers_edit_submit(request: Request, server_id: int):
    form = await request.form()
    payload = _get_server_form_payload(form)
    payload["is_active"] = 1 if form.get("is_active") else 0
    await update_server(server_id, **payload)
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/delete")
async def servers_delete(server_id: int):
    await delete_server(server_id)
    return RedirectResponse("/servers", status_code=303)


@router.get("/{server_id}/groups", response_class=HTMLResponse)
async def servers_groups(request: Request, server_id: int):
    """Fetch groups from a server and show them in the admin UI."""
    server = await get_server_by_id(server_id)
    if not server:
        return RedirectResponse("/servers", status_code=303)

    client = get_api_client(server)
    templates = get_templates()
    return templates.TemplateResponse(
        "servers.html",
        _server_page_context(
            request=request,
            servers=await _load_servers_for_page(),
            groups_server=server,
            groups_data=await _load_and_translate_groups(server),
            supports_multi_group=client.get_supports_multi_group(server),
        ),
    )


@router.get("/{server_id}/api/groups")
async def api_servers_groups(server_id: int):
    """Fetch groups from a server and return JSON."""
    server = await get_server_by_id(server_id)
    if not server:
        return JSONResponse({"success": False, "message": "Server not found"})

    client = get_api_client(server)
    manual_groups = server.get("manual_groups", "")
    if manual_groups:
        groups = {group["name"]: group for group in _build_manual_group_rows(manual_groups)}
        return JSONResponse(
            {
                "success": True,
                "data": groups,
                "supports_multi_group": client.get_supports_multi_group(server),
            }
        )

    groups = {
        group["name"]: group
        for group in await _load_and_translate_groups(server)
        if group.get("name")
    }
    return JSONResponse(
        {
            "success": True,
            "data": groups,
            "supports_multi_group": client.get_supports_multi_group(server),
        }
    )


@router.post("/preview-groups")
async def preview_groups(request: Request):
    """Preview groups from unsaved form data."""
    form = await request.form()
    server = _get_server_form_payload(form)
    if not server.get("name"):
        server["name"] = "Preview Server"

    client = get_api_client(server)
    return JSONResponse(
        {
            "success": True,
            "data": await _load_and_translate_groups(server),
            "supports_multi_group": client.get_supports_multi_group(server),
            "api_type": server.get("api_type", "newapi"),
        }
    )
