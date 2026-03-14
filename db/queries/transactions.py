"""
db/queries/transactions.py — Dedup MBBank transactionID.
Bảng processed_transactions ngăn xử lý trùng giao dịch.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def is_transaction_processed(transaction_id: str) -> bool:
    """Kiểm tra giao dịch đã được xử lý chưa."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM processed_transactions WHERE transaction_id = ?",
        (transaction_id,),
    )
    row = await cursor.fetchone()
    return row is not None


async def mark_transaction_processed(
    transaction_id: str,
    order_code: Optional[str] = None,
    amount: Optional[int] = None,
) -> None:
    """Đánh dấu giao dịch đã xử lý."""
    db = await get_db()
    await db.execute(
        """INSERT OR IGNORE INTO processed_transactions
           (transaction_id, order_code, amount)
           VALUES (?, ?, ?)""",
        (transaction_id, order_code, amount),
    )
    await db.commit()


async def get_processed_transactions(
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Lấy danh sách giao dịch đã xử lý (admin)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM processed_transactions
           ORDER BY id DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
