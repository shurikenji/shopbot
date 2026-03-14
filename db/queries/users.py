"""
db/queries/users.py — CRUD operations cho bảng users.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Lấy user theo Telegram ID."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """Lấy user theo internal ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_user(
    telegram_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> dict:
    """Tạo user mới, trả về user dict. Dùng INSERT OR IGNORE để tránh race condition."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT OR IGNORE INTO users (telegram_id, username, full_name)
           VALUES (?, ?, ?)""",
        (telegram_id, username, full_name),
    )
    await db.commit()
    if cursor.lastrowid and cursor.rowcount > 0:
        return await get_user_by_id(cursor.lastrowid)  # type: ignore[return-value]
    # Race condition: user đã được tạo bởi request khác
    return await get_user_by_telegram_id(telegram_id)  # type: ignore[return-value]


async def update_user(
    user_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> None:
    """Cập nhật username và full_name."""
    db = await get_db()
    await db.execute(
        """UPDATE users
           SET username = COALESCE(?, username),
               full_name = COALESCE(?, full_name),
               updated_at = datetime('now', '+7 hours')
           WHERE id = ?""",
        (username, full_name, user_id),
    )
    await db.commit()


async def set_admin(user_id: int, is_admin: int = 1) -> None:
    """Đặt/gỡ quyền admin."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET is_admin = ?, updated_at = datetime('now', '+7 hours') WHERE id = ?",
        (is_admin, user_id),
    )
    await db.commit()


async def set_banned(user_id: int, is_banned: int = 1) -> None:
    """Ban/unban user."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET is_banned = ?, updated_at = datetime('now', '+7 hours') WHERE id = ?",
        (is_banned, user_id),
    )
    await db.commit()


async def get_all_users(
    offset: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
) -> list[dict]:
    """Lấy danh sách users (phân trang, tìm kiếm)."""
    db = await get_db()
    if search:
        cursor = await db.execute(
            """SELECT * FROM users
               WHERE username LIKE ? OR full_name LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (f"%{search}%", f"%{search}%", f"%{search}%", limit, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_users(search: Optional[str] = None) -> int:
    """Đếm tổng số users."""
    db = await get_db()
    if search:
        cursor = await db.execute(
            """SELECT COUNT(*) FROM users
               WHERE username LIKE ? OR full_name LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?""",
            (f"%{search}%", f"%{search}%", f"%{search}%"),
        )
    else:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
    row = await cursor.fetchone()
    return row[0] if row else 0


async def get_all_user_telegram_ids() -> list[int]:
    """Lấy tất cả Telegram IDs (dùng cho broadcast)."""
    db = await get_db()
    cursor = await db.execute("SELECT telegram_id FROM users WHERE is_banned = 0")
    rows = await cursor.fetchall()
    return [row[0] for row in rows]
