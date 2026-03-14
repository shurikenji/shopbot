"""
db/queries/categories.py — CRUD operations cho bảng categories.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def get_active_categories() -> list[dict]:
    """Lấy danh mục đang active, sắp xếp theo sort_order."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM categories
           WHERE is_active = 1
           ORDER BY sort_order ASC, id ASC"""
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_categories() -> list[dict]:
    """Lấy tất cả danh mục (admin)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM categories ORDER BY sort_order ASC, id ASC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_category_by_id(cat_id: int) -> Optional[dict]:
    """Lấy danh mục theo ID."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM categories WHERE id = ?", (cat_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_category(
    name: str,
    icon: str = "📦",
    description: Optional[str] = None,
    cat_type: str = "general",
    sort_order: int = 0,
) -> int:
    """Tạo danh mục mới, trả về ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO categories (name, icon, description, cat_type, sort_order)
           VALUES (?, ?, ?, ?, ?)""",
        (name, icon, description, cat_type, sort_order),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def update_category(
    cat_id: int,
    name: Optional[str] = None,
    icon: Optional[str] = None,
    description: Optional[str] = None,
    cat_type: Optional[str] = None,
    sort_order: Optional[int] = None,
    is_active: Optional[int] = None,
) -> None:
    """Cập nhật danh mục."""
    db = await get_db()
    fields = []
    values = []

    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if icon is not None:
        fields.append("icon = ?")
        values.append(icon)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if cat_type is not None:
        fields.append("cat_type = ?")
        values.append(cat_type)
    if sort_order is not None:
        fields.append("sort_order = ?")
        values.append(sort_order)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(is_active)

    if not fields:
        return

    fields.append("updated_at = datetime('now', '+7 hours')")
    values.append(cat_id)

    query = f"UPDATE categories SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, tuple(values))
    await db.commit()


async def delete_category(cat_id: int) -> None:
    """Xóa danh mục (hard delete)."""
    db = await get_db()
    await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    await db.commit()
