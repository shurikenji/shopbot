"""
admin/routers/categories.py - Category CRUD routes.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from admin.deps import get_templates, protected_router
from db.queries.categories import (
    create_category,
    delete_category,
    get_all_categories,
    get_category_by_id,
    update_category,
)

router = protected_router(prefix="/categories", tags=["categories"])


@router.get("", response_class=HTMLResponse)
async def categories_list(request: Request):
    templates = get_templates()
    return templates.TemplateResponse(
        "categories.html",
        {"request": request, "categories": await get_all_categories()},
    )


@router.post("/add")
async def categories_add(request: Request):
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
async def categories_edit_page(request: Request, cat_id: Annotated[int, Path()]):
    category = await get_category_by_id(cat_id)
    if not category:
        return RedirectResponse("/categories", status_code=303)

    templates = get_templates()
    return templates.TemplateResponse(
        "categories.html",
        {
            "request": request,
            "categories": await get_all_categories(),
            "editing": category,
        },
    )


@router.post("/{cat_id}/edit")
async def categories_edit_submit(request: Request, cat_id: Annotated[int, Path()]):
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
async def categories_delete(cat_id: Annotated[int, Path()]):
    await delete_category(cat_id)
    return RedirectResponse("/categories", status_code=303)
