"""
admin/routers/categories.py — CRUD danh mục.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from db.queries.categories import (
    get_all_categories, get_category_by_id,
    create_category, update_category, delete_category,
)

router = APIRouter(prefix="/categories", tags=["categories"])


def _check(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
async def categories_list(request: Request):
    r = _check(request)
    if r: return r
    categories = await get_all_categories()
    templates = get_templates()
    return templates.TemplateResponse(
        "categories.html", {"request": request, "categories": categories}
    )


@router.post("/add")
async def categories_add(request: Request):
    r = _check(request)
    if r: return r
    form = await request.form()
    await create_category(
        name=form["name"],
        icon=form.get("icon", "📦"),
        cat_type=form.get("cat_type", "general"),
        description=form.get("description"),
        sort_order=int(form.get("sort_order", 0)),
    )
    return RedirectResponse("/categories", status_code=303)


@router.get("/{cat_id}/edit", response_class=HTMLResponse)
async def categories_edit_page(request: Request, cat_id: int):
    r = _check(request)
    if r: return r
    cat = await get_category_by_id(cat_id)
    if not cat:
        return RedirectResponse("/categories", status_code=303)
    templates = get_templates()
    return templates.TemplateResponse(
        "categories.html",
        {"request": request, "categories": await get_all_categories(), "editing": cat},
    )


@router.post("/{cat_id}/edit")
async def categories_edit_submit(request: Request, cat_id: int):
    r = _check(request)
    if r: return r
    form = await request.form()
    await update_category(
        cat_id,
        name=form.get("name"),
        icon=form.get("icon"),
        cat_type=form.get("cat_type"),
        description=form.get("description"),
        sort_order=int(form.get("sort_order", 0)) if form.get("sort_order") else None,
        is_active=1 if form.get("is_active") else 0,
    )
    return RedirectResponse("/categories", status_code=303)


@router.get("/{cat_id}/delete")
async def categories_delete(request: Request, cat_id: int):
    r = _check(request)
    if r: return r
    await delete_category(cat_id)
    return RedirectResponse("/categories", status_code=303)
