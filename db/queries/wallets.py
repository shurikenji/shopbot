"""
db/queries/wallets.py — CRUD operations cho bảng wallets + wallet_transactions.
Tiền tệ luôn dùng INTEGER (VNĐ).
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def get_wallet(user_id: int) -> Optional[dict]:
    """Lấy ví của user."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM wallets WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def ensure_wallet(user_id: int) -> dict:
    """Tạo ví nếu chưa có, trả về ví hiện tại."""
    wallet = await get_wallet(user_id)
    if wallet:
        return wallet

    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)",
        (user_id,),
    )
    await db.commit()
    return await get_wallet(user_id)  # type: ignore[return-value]


async def get_balance(user_id: int) -> int:
    """Lấy số dư ví (tạo ví nếu chưa có)."""
    wallet = await ensure_wallet(user_id)
    return wallet["balance"]


async def add_balance(
    user_id: int,
    amount: int,
    tx_type: str,
    reference_id: Optional[str] = None,
    description: Optional[str] = None,
) -> int:
    """
    Cộng tiền vào ví (amount dương = cộng, âm = trừ).
    Trả về balance sau khi thay đổi.
    Tạo wallet_transaction để audit.
    """
    db = await get_db()
    wallet = await ensure_wallet(user_id)
    new_balance = wallet["balance"] + amount

    # Cập nhật balance
    await db.execute(
        """UPDATE wallets
           SET balance = ?, updated_at = datetime('now', '+7 hours')
           WHERE user_id = ?""",
        (new_balance, user_id),
    )

    # Ghi lịch sử giao dịch
    await db.execute(
        """INSERT INTO wallet_transactions
           (user_id, amount, balance_after, type, reference_id, description)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, amount, new_balance, tx_type, reference_id, description),
    )

    await db.commit()
    return new_balance


async def deduct_balance(
    user_id: int,
    amount: int,
    reference_id: Optional[str] = None,
    description: Optional[str] = None,
) -> int:
    """
    Trừ tiền từ ví. amount phải > 0.
    Trả về balance mới.
    Raises ValueError nếu không đủ tiền.
    """
    balance = await get_balance(user_id)
    if balance < amount:
        raise ValueError(
            f"Số dư không đủ: hiện có {balance}₫, cần {amount}₫"
        )
    return await add_balance(
        user_id, -amount, "purchase", reference_id, description
    )


async def get_wallet_transactions(
    user_id: int,
    offset: int = 0,
    limit: int = 10,
) -> list[dict]:
    """Lấy lịch sử giao dịch ví (mới nhất trước)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM wallet_transactions
           WHERE user_id = ?
           ORDER BY id DESC LIMIT ? OFFSET ?""",
        (user_id, limit, offset),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_wallet_transactions(user_id: int) -> int:
    """Đếm tổng giao dịch ví."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM wallet_transactions WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    return row[0] if row else 0
