"""
admin/routers/products.py - CRUD san pham + auto-generate tu server.
"""
from __future__ import annotations

from urllib.parse import urlencode

import aiosqlite
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from bot.services.api_clients import get_api_client
from db.queries.categories import get_all_categories
from db.queries.products import (
    create_product,
    delete_product,
    get_all_products,
    get_product_by_id,
    get_product_delete_dependencies,
    update_product,
)
from db.queries.servers import get_all_servers

router = APIRouter(prefix="/products", tags=["products"])

PRODUCT_TYPE_META = {
    "key_new": ("New Key", "info"),
    "key_topup": ("Top Up", "success"),
    "account_stocked": ("Stock Account", "warning"),
    "service_upgrade": ("Service", "secondary"),
}


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


def _build_flash_context(request: Request) -> dict:
    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    if msg == "deleted":
        return {
            "flash_message": "Da xoa san pham thanh cong.",
            "flash_type": "success",
        }

    if msg.startswith("generated_"):
        generated_count = msg.split("_", 1)[1]
        return {
            "flash_message": f"Da tao tu dong {generated_count} san pham tu server.",
            "flash_type": "success",
        }

    if error == "not_found":
        return {
            "flash_message": "San pham khong ton tai hoac da bi xoa.",
            "flash_type": "warning",
        }

    if error == "no_key_category":
        return {
            "flash_message": "Khong tim thay danh muc co cat_type = key_api de auto-generate.",
            "flash_type": "warning",
        }

    if error == "in_use":
        orders = int(request.query_params.get("orders", 0))
        account_stocks = int(request.query_params.get("account_stocks", 0))
        chatgpt_accounts = int(request.query_params.get("chatgpt_accounts", 0))
        blockers = []
        if orders:
            blockers.append(f"{orders} order")
        if account_stocks:
            blockers.append(f"{account_stocks} account stock")
        if chatgpt_accounts:
            blockers.append(f"{chatgpt_accounts} legacy account")

        detail = ", ".join(blockers) if blockers else "du lieu lien quan"
        return {
            "flash_message": f"Khong the xoa san pham vi con {detail}. Hay tat san pham thay vi xoa cung.",
            "flash_type": "danger",
        }

    if error == "delete_failed":
        return {
            "flash_message": "Xoa san pham that bai do loi rang buoc du lieu.",
            "flash_type": "danger",
        }

    return {}


def _decorate_products(products: list[dict], categories: list[dict], servers: list[dict]) -> None:
    cat_map = {category["id"]: category["name"] for category in categories}
    srv_map = {server["id"]: server for server in servers}

    for product in products:
        product["cat_name"] = cat_map.get(product["category_id"], "-")
        server = srv_map.get(product.get("server_id")) if product.get("server_id") else None
        product["srv_name"] = server["name"] if server else "-"
        product["server_default_group"] = (server.get("default_group") or "").strip() if server else ""
        product_group = (product.get("group_name") or "").strip()
        uses_server_default_group = (
            product.get("product_type") == "key_new"
            and not product_group
            and bool(product["server_default_group"])
        )
        product["uses_server_default_group"] = uses_server_default_group
        product["effective_group_name"] = (
            product_group if product_group else product["server_default_group"] if uses_server_default_group else ""
        )
        type_label, type_theme = PRODUCT_TYPE_META.get(
            product.get("product_type", ""),
            ("Other", "secondary"),
        )
        product["type_label"] = type_label
        product["type_theme"] = type_theme

        description = (product.get("description") or "").strip()
        product["description_short"] = (
            description[:96] + ("..." if len(description) > 96 else "")
            if description
            else ""
        )


@router.get("", response_class=HTMLResponse)
async def products_list(request: Request):
    r = _check(request)
    if r:
        return r

    products = await get_all_products(limit=200)
    categories = await get_all_categories()
    servers = await get_all_servers()
    _decorate_products(products, categories, servers)

    templates = get_templates()
    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "products": products,
            "categories": categories,
            "servers": servers,
            **_build_flash_context(request),
        },
    )


@router.post("/add")
async def products_add(request: Request):
    r = _check(request)
    if r:
        return r

    form = await request.form()
    await create_product(
        category_id=int(form["category_id"]),
        name=form["name"],
        price_vnd=int(form["price_vnd"]),
        product_type=form["product_type"],
        server_id=int(form["server_id"]) if form.get("server_id") else None,
        description=form.get("description"),
        quota_amount=int(form.get("quota_amount", 0)),
        dollar_amount=float(form.get("dollar_amount", 0)),
        group_name=form.get("group_name") or None,
        stock=int(form.get("stock", -1)),
        format_template=form.get("format_template") or None,
        input_prompt=form.get("input_prompt") or None,
    )
    return RedirectResponse("/products", status_code=303)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def products_edit_page(request: Request, product_id: int):
    r = _check(request)
    if r:
        return r

    product = await get_product_by_id(product_id)
    if not product:
        return RedirectResponse("/products?error=not_found", status_code=303)

    products = await get_all_products(limit=200)
    categories = await get_all_categories()
    servers = await get_all_servers()
    _decorate_products(products, categories, servers)

    templates = get_templates()
    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "products": products,
            "categories": categories,
            "servers": servers,
            "editing": product,
            **_build_flash_context(request),
        },
    )


@router.post("/{product_id}/edit")
async def products_edit_submit(request: Request, product_id: int):
    r = _check(request)
    if r:
        return r

    form = await request.form()
    await update_product(
        product_id,
        category_id=int(form["category_id"]) if form.get("category_id") else None,
        name=form.get("name"),
        price_vnd=int(form["price_vnd"]) if form.get("price_vnd") else None,
        product_type=form.get("product_type"),
        server_id=int(form["server_id"]) if form.get("server_id") else None,
        description=form.get("description"),
        quota_amount=int(form.get("quota_amount", 0)),
        dollar_amount=float(form.get("dollar_amount", 0)),
        group_name=form.get("group_name") or None,
        stock=int(form.get("stock", -1)),
        is_active=1 if form.get("is_active") else 0,
        format_template=form.get("format_template") or None,
        input_prompt=form.get("input_prompt") or None,
    )
    return RedirectResponse("/products", status_code=303)


@router.get("/{product_id}/delete")
async def products_delete(request: Request, product_id: int):
    r = _check(request)
    if r:
        return r

    product = await get_product_by_id(product_id)
    if not product:
        return RedirectResponse("/products?error=not_found", status_code=303)

    dependencies = await get_product_delete_dependencies(product_id)
    if dependencies["total"] > 0:
        query = urlencode(
            {
                "error": "in_use",
                "orders": dependencies["orders"],
                "account_stocks": dependencies["account_stocks"],
                "chatgpt_accounts": dependencies["chatgpt_accounts"],
            }
        )
        return RedirectResponse(f"/products?{query}", status_code=303)

    try:
        await delete_product(product_id)
    except aiosqlite.IntegrityError:
        dependencies = await get_product_delete_dependencies(product_id)
        if dependencies["total"] > 0:
            query = urlencode(
                {
                    "error": "in_use",
                    "orders": dependencies["orders"],
                    "account_stocks": dependencies["account_stocks"],
                    "chatgpt_accounts": dependencies["chatgpt_accounts"],
                }
            )
            return RedirectResponse(f"/products?{query}", status_code=303)
        return RedirectResponse("/products?error=delete_failed", status_code=303)

    return RedirectResponse("/products?msg=deleted", status_code=303)


@router.get("/auto-generate", response_class=HTMLResponse)
async def auto_generate(request: Request):
    """
    Auto-generate san pham tu server.
    Lay groups tu moi active server -> tao san pham key_new + key_topup cho moi group.
    """
    r = _check(request)
    if r:
        return r

    servers = await get_all_servers()
    categories = await get_all_categories()

    key_category = next((category for category in categories if category["cat_type"] == "key_api"), None)
    if not key_category:
        return RedirectResponse("/products?error=no_key_category", status_code=303)

    count = 0
    for server in servers:
        if not server["is_active"]:
            continue

        groups = await get_api_client(server).get_groups(server)
        if not groups:
            continue

        for group_info in groups:
            group_name = (group_info.get("name") or "").strip()
            if not group_name:
                continue

            description = group_info.get("desc_en") or group_info.get("desc") or ""

            await create_product(
                category_id=key_category["id"],
                name=f"{server['name']} - {group_name}",
                price_vnd=server["price_per_unit"],
                product_type="key_new",
                server_id=server["id"],
                quota_amount=server["quota_per_unit"],
                dollar_amount=server["dollar_per_unit"],
                group_name=group_name,
                description=description,
            )
            count += 1

            await create_product(
                category_id=key_category["id"],
                name=f"{server['name']} - {group_name} (Top Up)",
                price_vnd=server["price_per_unit"],
                product_type="key_topup",
                server_id=server["id"],
                quota_amount=server["quota_per_unit"],
                dollar_amount=server["dollar_per_unit"],
                group_name=None,
                description=description,
            )
            count += 1

    return RedirectResponse(f"/products?msg=generated_{count}", status_code=303)
