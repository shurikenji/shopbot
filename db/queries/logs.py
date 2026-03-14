"""
db/queries/logs.py — CRUD cho bảng logs.
Ghi log hoạt động hệ thống (payment, order processing, errors).
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def add_log(
    message: str,
    level: str = "info",
    module: Optional[str] = None,
    detail: Optional[str] = None,
) -> int:
    """Ghi log mới, trả về ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO logs (level, module, message, detail)
           VALUES (?, ?, ?, ?)""",
        (level, module, message, detail),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_logs(
    offset: int = 0,
    limit: int = 50,
    level: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    """Lấy logs (mới nhất trước, phân trang, filter)."""
    db = await get_db()
    query = "SELECT * FROM logs WHERE 1=1"
    params: list = []

    if level:
        query += " AND level = ?"
        params.append(level)
    if module:
        query += " AND module = ?"
        params.append(module)
    if search:
        query += " AND (message LIKE ? OR detail LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_logs(
    level: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
) -> int:
    """Đếm tổng logs."""
    db = await get_db()
    query = "SELECT COUNT(*) FROM logs WHERE 1=1"
    params: list = []

    if level:
        query += " AND level = ?"
        params.append(level)
    if module:
        query += " AND module = ?"
        params.append(module)
    if search:
        query += " AND (message LIKE ? OR detail LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    cursor = await db.execute(query, tuple(params))
    row = await cursor.fetchone()
    return row[0] if row else 0


async def clear_old_logs(days: int = 30) -> int:
    """Xóa logs cũ hơn N ngày, trả về số lượng đã xóa."""
    db = await get_db()
    cursor = await db.execute(
        """DELETE FROM logs
           WHERE created_at < datetime('now', ? || ' days')""",
        (f"-{days}",),
    )
    await db.commit()
    return cursor.rowcount
