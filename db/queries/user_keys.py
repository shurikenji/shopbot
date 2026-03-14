"""
db/queries/user_keys.py — CRUD cho bảng user_keys (Keys của tôi).
Lưu trữ API keys mà user đã mua hoặc đăng ký.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def get_user_keys(
    user_id: int,
    server_id: Optional[int] = None,
    active_only: bool = True,
) -> list[dict]:
    """Lấy danh sách keys của user, optional filter theo server."""
    db = await get_db()
    query = "SELECT * FROM user_keys WHERE user_id = ?"
    params: list = [user_id]

    if server_id is not None:
        query += " AND server_id = ?"
        params.append(server_id)
    if active_only:
        query += " AND is_active = 1"

    query += " ORDER BY id DESC"
    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_user_key_by_id(key_id: int) -> Optional[dict]:
    """Lấy user key theo ID."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM user_keys WHERE id = ?", (key_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_user_key(
    user_id: int,
    server_id: int,
    api_key: str,
    api_token_id: Optional[int] = None,
    label: Optional[str] = None,
) -> int:
    """Tạo user key mới, trả về ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO user_keys
           (user_id, server_id, api_key, api_token_id, label)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, server_id, api_key, api_token_id, label),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def update_user_key(
    key_id: int,
    label: Optional[str] = None,
    is_active: Optional[int] = None,
    api_token_id: Optional[int] = None,
) -> None:
    """Cập nhật user key."""
    db = await get_db()
    fields = []
    values = []

    if label is not None:
        fields.append("label = ?")
        values.append(label)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(is_active)
    if api_token_id is not None:
        fields.append("api_token_id = ?")
        values.append(api_token_id)

    if not fields:
        return

    fields.append("updated_at = datetime('now', '+7 hours')")
    values.append(key_id)

    query = f"UPDATE user_keys SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, tuple(values))
    await db.commit()


async def find_user_key_by_api_key(
    user_id: int,
    api_key: str,
) -> Optional[dict]:
    """Tìm user key theo api_key string (kiểm tra trùng)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM user_keys WHERE user_id = ? AND api_key = ?",
        (user_id, api_key),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def upsert_user_key(
    user_id: int,
    server_id: int,
    api_key: str,
    api_token_id: Optional[int] = None,
    label: Optional[str] = None,
) -> int:
    """
    Tạo hoặc cập nhật user key.
    Nếu key đã tồn tại cho user → update label/token_id.
    Nếu chưa → tạo mới.
    Returns key ID.
    """
    existing = await find_user_key_by_api_key(user_id, api_key)
    if existing:
        await update_user_key(
            existing["id"],
            label=label,
            api_token_id=api_token_id,
        )
        return existing["id"]
    return await create_user_key(
        user_id=user_id,
        server_id=server_id,
        api_key=api_key,
        api_token_id=api_token_id,
        label=label,
    )
