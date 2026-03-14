"""
admin/routers/users.py — Xem users + detail + adjust wallet.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.users import (
    get_all_users, count_users, get_user_by_id,
    set_admin, set_banned,
)
from db.queries.wallets import ensure_wallet, add_balance
from db.queries.orders import get_orders_by_user

router = APIRouter(prefix="/users", tags=["users"])


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
async def users_list(request: Request):
    r = _check(request)
    if r: return r

    page = int(request.query_params.get("page", 0))
    search = request.query_params.get("search", "")
    per_page = 20

    users = await get_all_users(
        offset=page * per_page, limit=per_page,
        search=search or None,
    )
    total = await count_users(search=search or None)
    total_pages = max(1, math.ceil(total / per_page))

    templates = get_templates()
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users,
         "page": page, "total_pages": total_pages,
         "filter_search": search},
    )


@router.get("/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int):
    r = _check(request)
    if r: return r
    user = await get_user_by_id(user_id)
    if not user:
        return RedirectResponse("/users", status_code=303)

    wallet = await ensure_wallet(user_id)
    recent_orders = await get_orders_by_user(user_id, limit=10)

    templates = get_templates()
    return templates.TemplateResponse(
        "user_detail.html",
        {"request": request, "user": user,
         "wallet": wallet, "recent_orders": recent_orders},
    )


@router.post("/{user_id}/adjust-wallet")
async def adjust_wallet(request: Request, user_id: int):
    """Admin điều chỉnh số dư ví."""
    r = _check(request)
    if r: return r
    form = await request.form()
    amount = int(form.get("amount", 0))
    description = form.get("description", "Admin điều chỉnh")

    if amount != 0:
        await add_balance(
            user_id=user_id,
            amount=amount,
            tx_type="admin_adjust",
            description=description,
        )

    return RedirectResponse(f"/users/{user_id}", status_code=303)


@router.get("/{user_id}/toggle-admin")
async def toggle_admin(request: Request, user_id: int):
    r = _check(request)
    if r: return r
    user = await get_user_by_id(user_id)
    if user:
        await set_admin(user_id, 0 if user["is_admin"] else 1)
    return RedirectResponse(f"/users/{user_id}", status_code=303)


@router.get("/{user_id}/toggle-ban")
async def toggle_ban(request: Request, user_id: int):
    r = _check(request)
    if r: return r
    user = await get_user_by_id(user_id)
    if user:
        await set_banned(user_id, 0 if user["is_banned"] else 1)
    return RedirectResponse(f"/users/{user_id}", status_code=303)
