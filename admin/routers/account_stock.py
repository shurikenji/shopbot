"""
admin/routers/account_stock.py — CRUD kho tài khoản chung.
Chỉ hỗ trợ product_type = account_stocked.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.account_stocks import (
    get_accounts_by_product, count_stock,
    add_account, bulk_add_accounts, delete_account,
)
from db.queries.products import get_all_products
from db.queries.categories import get_all_categories

router = APIRouter(prefix="/account-stock", tags=["account_stock"])

_STOCK_TYPES = ("account_stocked",)


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
async def account_stock_page(request: Request):
    r = _check(request)
    if r: return r

    # Lấy danh mục (để hiện badge)
    categories = await get_all_categories()
    cat_map = {c["id"]: c for c in categories}

    # Lấy tất cả sản phẩm thuộc nhóm có stock
    all_products = await get_all_products(limit=200)
    stock_products = [
        p for p in all_products
        if p["product_type"] in _STOCK_TYPES
    ]

    # Lấy stock cho từng product, gắn thông tin danh mục
    stock_by_product = {}
    for p in stock_products:
        stock_info = await count_stock(p["id"])
        accounts = await get_accounts_by_product(p["id"], limit=50)
        cat = cat_map.get(p.get("category_id"), {})
        stock_by_product[p["id"]] = {
            "product_name": p["name"],
            "product_type": p["product_type"],
            "format_template": p.get("format_template") or "",
            "cat_name": cat.get("name", ""),
            "cat_icon": cat.get("icon", "📁"),
            **stock_info,
            "accounts": accounts,
        }

    templates = get_templates()
    return templates.TemplateResponse(
        "account_stock.html",
        {"request": request,
         "stock_by_product": stock_by_product,
         "stock_products": stock_products,
         "cat_map": cat_map},
    )


@router.post("/add")
async def account_stock_add(request: Request):
    """Thêm tài khoản — hỗ trợ bulk (mỗi dòng 1 account)."""
    r = _check(request)
    if r: return r
    form = await request.form()
    product_id = int(form["product_id"])
    raw_data = form.get("accounts_data", "")

    # Tách từng dòng (hỗ trợ bulk add)
    lines = [line.strip() for line in raw_data.strip().split("\n") if line.strip()]

    if len(lines) == 1:
        await add_account(product_id, lines[0])
    elif len(lines) > 1:
        await bulk_add_accounts(product_id, lines)

    return RedirectResponse("/account-stock", status_code=303)


@router.get("/{account_id}/delete")
async def account_stock_delete(request: Request, account_id: int):
    r = _check(request)
    if r: return r
    await delete_account(account_id)
    return RedirectResponse("/account-stock", status_code=303)
