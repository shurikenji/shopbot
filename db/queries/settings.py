"""
db/queries/settings.py — CRUD cho bảng settings (key-value store).
Được dùng để lưu cấu hình MB Bank, VietQR, Bot, v.v.
Ưu tiên: settings DB > .env fallback.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Lấy giá trị setting theo key."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    )
    row = await cursor.fetchone()
    if row and row[0]:
        return row[0]
    return default


async def get_setting_int(key: str, default: int = 0) -> int:
    """Lấy setting dạng integer."""
    val = await get_setting(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


async def set_setting(key: str, value: str, description: Optional[str] = None) -> None:
    """Tạo hoặc cập nhật setting."""
    db = await get_db()
    if description is not None:
        await db.execute(
            """INSERT INTO settings (key, value, description, updated_at)
               VALUES (?, ?, ?, datetime('now', '+7 hours'))
               ON CONFLICT(key) DO UPDATE
               SET value = excluded.value,
                   description = excluded.description,
                   updated_at = datetime('now', '+7 hours')""",
            (key, value, description),
        )
    else:
        await db.execute(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now', '+7 hours'))
               ON CONFLICT(key) DO UPDATE
               SET value = excluded.value,
                   updated_at = datetime('now', '+7 hours')""",
            (key, value),
        )
    await db.commit()


async def get_all_settings() -> list[dict]:
    """Lấy tất cả settings."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM settings ORDER BY key ASC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_settings_dict() -> dict[str, str]:
    """Lấy tất cả settings dưới dạng dict key→value."""
    settings = await get_all_settings()
    return {s["key"]: s["value"] for s in settings}


async def delete_setting(key: str) -> None:
    """Xóa setting."""
    db = await get_db()
    await db.execute("DELETE FROM settings WHERE key = ?", (key,))
    await db.commit()
