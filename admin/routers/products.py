"""
admin/routers/products.py - CRUD sản phẩm.
"""
from __future__ import annotations

from urllib.parse import urlencode

import aiosqlite
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates, protected_router
from db.queries.categories import get_all_categories, get_category_by_id
from db.queries.products import (
    create_product,
    delete_product,
    get_all_products,
    get_product_by_id,
    get_product_delete_dependencies,
    update_product,
)
from db.queries.servers import get_all_servers

router = protected_router(prefix="/products", tags=["products"])

PRODUCT_TYPE_META = {
    "key_new": ("New Key", "info"),
    "key_topup": ("Top Up", "success"),
    "account_stocked": ("Stock Account", "warning"),
    "service_upgrade": ("Service", "secondary"),
}
KEY_API_PRODUCT_TYPES = {"key_new", "key_topup"}
GENERAL_PRODUCT_TYPES = {"account_stocked", "service_upgrade"}


def _build_flash_context(request: Request) -> dict:
    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    if msg == "deleted":
        return {
            "flash_message": "Đã xoá sản phẩm thành công.",
            "flash_type": "success",
        }

    if error == "not_found":
        return {
            "flash_message": "Sản phẩm không tồn tại hoặc đã bị xoá.",
            "flash_type": "warning",
        }

    if error == "invalid_category":
        return {
            "flash_message": "Danh mục không tồn tại hoặc đã bị xoá.",
            "flash_type": "danger",
        }

    if error == "invalid_product_type":
        return {
            "flash_message": "Loại sản phẩm không hợp lệ với danh mục đã chọn.",
            "flash_type": "danger",
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

        detail = ", ".join(blockers) if blockers else "dữ liệu liên quan"
        return {
            "flash_message": f"Không thể xoá sản phẩm vì còn {detail}. Hãy tắt sản phẩm thay vì xoá cứng.",
            "flash_type": "danger",
        }

    if error == "delete_failed":
        return {
            "flash_message": "Xoá sản phẩm thất bại do lỗi ràng buộc dữ liệu.",
            "flash_type": "danger",
        }

    return {}


def _get_allowed_product_types(category: dict | None) -> set[str]:
    if not category:
        return set()
    if category.get("cat_type") == "key_api":
        return KEY_API_PRODUCT_TYPES
    return GENERAL_PRODUCT_TYPES


def _build_form_redirect(product_id: int | None, error: str) -> RedirectResponse:
    target = f"/products/{product_id}/edit" if product_id else "/products"
    separator = "&" if "?" in target else "?"
    return RedirectResponse(f"{target}{separator}error={error}", status_code=303)


async def _build_product_payload(
    form,
    product_id: int | None = None,
) -> tuple[dict | None, RedirectResponse | None]:
    category_id = int(form["category_id"])
    category = await get_category_by_id(category_id)
    if not category:
        return None, _build_form_redirect(product_id, "invalid_category")

    product_type = (form.get("product_type") or "").strip()
    if product_type not in _get_allowed_product_types(category):
        return None, _build_form_redirect(product_id, "invalid_product_type")

    is_key = product_type in KEY_API_PRODUCT_TYPES
    is_key_new = product_type == "key_new"
    is_account = product_type == "account_stocked"
    is_service = product_type == "service_upgrade"

    payload = {
        "category_id": category_id,
        "name": form["name"],
        "price_vnd": int(form["price_vnd"]),
        "product_type": product_type,
        "server_id": int(form["server_id"]) if is_key and form.get("server_id") else None,
        "description": form.get("description"),
        "quota_amount": int(form.get("quota_amount", 0)) if is_key else 0,
        "dollar_amount": float(form.get("dollar_amount", 0)) if is_key else 0.0,
        "group_name": (form.get("group_name") or None) if is_key_new else None,
        "stock": int(form.get("stock", -1)),
        "format_template": (form.get("format_template") or None) if is_account else None,
        "input_prompt": (form.get("input_prompt") or None) if is_service else None,
    }
    return payload, None


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
    form = await request.form()
    payload, error_redirect = await _build_product_payload(form)
    if error_redirect:
        return error_redirect
    await create_product(**payload)
    return RedirectResponse("/products", status_code=303)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def products_edit_page(request: Request, product_id: int):
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
    form = await request.form()
    payload, error_redirect = await _build_product_payload(form, product_id=product_id)
    if error_redirect:
        return error_redirect
    await update_product(
        product_id,
        category_id=payload["category_id"],
        name=payload["name"],
        price_vnd=payload["price_vnd"],
        product_type=payload["product_type"],
        server_id=payload["server_id"],
        description=payload["description"],
        quota_amount=payload["quota_amount"],
        dollar_amount=payload["dollar_amount"],
        group_name=payload["group_name"],
        stock=payload["stock"],
        is_active=1 if form.get("is_active") else 0,
        format_template=payload["format_template"],
        input_prompt=payload["input_prompt"],
    )
    return RedirectResponse("/products", status_code=303)


@router.get("/{product_id}/delete")
async def products_delete(product_id: int):
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
