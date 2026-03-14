"""
db/queries/orders.py — CRUD operations cho bảng orders.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def create_order(
    order_code: str,
    user_id: int,
    product_type: str,
    amount: int,
    payment_method: str,
    product_id: Optional[int] = None,
    product_name: Optional[str] = None,
    server_id: Optional[int] = None,
    group_name: Optional[str] = None,
    existing_key: Optional[str] = None,
    custom_quota: Optional[int] = None,
    qr_content: Optional[str] = None,
    expired_at: Optional[str] = None,
) -> int:
    """Tạo đơn hàng mới, trả về ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO orders
           (order_code, user_id, product_id, product_name, product_type,
            amount, payment_method, server_id, group_name, existing_key,
            custom_quota, qr_content, expired_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            order_code, user_id, product_id, product_name, product_type,
            amount, payment_method, server_id, group_name, existing_key,
            custom_quota, qr_content, expired_at,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_order_by_id(order_id: int) -> Optional[dict]:
    """Lấy đơn hàng theo ID."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_order_by_code(order_code: str) -> Optional[dict]:
    """Lấy đơn hàng theo mã đơn."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM orders WHERE order_code = ?", (order_code,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_orders_by_user(
    user_id: int,
    offset: int = 0,
    limit: int = 10,
) -> list[dict]:
    """Lấy đơn hàng của user (mới nhất trước)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM orders
           WHERE user_id = ?
           ORDER BY id DESC LIMIT ? OFFSET ?""",
        (user_id, limit, offset),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_orders_by_user(user_id: int) -> int:
    """Đếm tổng đơn của user."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def get_pending_orders() -> list[dict]:
    """Lấy tất cả đơn pending (chưa thanh toán)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM orders WHERE status = 'pending' ORDER BY id ASC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_pending_qr_orders() -> list[dict]:
    """Lấy đơn pending thanh toán QR (dùng cho payment poller)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM orders
           WHERE status = 'pending' AND payment_method = 'qr'
           ORDER BY id ASC"""
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_order_status(
    order_id: int,
    status: str,
    **kwargs,
) -> None:
    """Cập nhật trạng thái đơn hàng + optional fields."""
    db = await get_db()
    allowed_fields = {
        "api_key", "api_token_id", "quota_before", "quota_after",
        "delivery_info", "user_input_data", "mb_transaction_id",
        "paid_at", "is_refunded", "refund_reason", "refunded_at",
        "expired_at",
    }

    fields = ["status = ?", "updated_at = datetime('now')"]
    values: list = [status]

    for key, val in kwargs.items():
        if key in allowed_fields:
            fields.append(f"{key} = ?")
            values.append(val)

    values.append(order_id)
    query = f"UPDATE orders SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, tuple(values))
    await db.commit()


async def cancel_order(order_id: int) -> None:
    """Hủy đơn hàng và nhả tài khoản (nếu có)."""
    await update_order_status(order_id, "cancelled")
    from db.queries.account_stocks import release_account_by_order
    await release_account_by_order(order_id)


async def expire_order(order_id: int) -> None:
    """Đánh dấu đơn hết hạn và nhả tài khoản (nếu có)."""
    from datetime import datetime as _dt
    await update_order_status(
        order_id, "expired", expired_at=_dt.utcnow().isoformat()
    )
    from db.queries.account_stocks import release_account_by_order
    await release_account_by_order(order_id)


async def mark_refunded(
    order_id: int,
    reason: Optional[str] = None,
) -> None:
    """Đánh dấu đã hoàn tiền (chống hoàn 2 lần)."""
    db = await get_db()
    await db.execute(
        """UPDATE orders
           SET is_refunded = 1, refund_reason = ?, refunded_at = datetime('now'),
               status = 'refunded', updated_at = datetime('now')
           WHERE id = ? AND is_refunded = 0""",
        (reason, order_id),
    )
    await db.commit()


async def get_all_orders(
    offset: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    """Lấy tất cả đơn hàng (admin, phân trang)."""
    db = await get_db()
    query = "SELECT * FROM orders WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (order_code LIKE ? OR product_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_all_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> int:
    """Đếm tổng đơn hàng (admin)."""
    db = await get_db()
    query = "SELECT COUNT(*) FROM orders WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (order_code LIKE ? OR product_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    cursor = await db.execute(query, tuple(params))
    row = await cursor.fetchone()
    return row[0] if row else 0


async def get_order_stats() -> dict:
    """Thống kê đơn hàng cho dashboard."""
    db = await get_db()

    # Tổng doanh thu đơn completed
    cursor = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'completed'"
    )
    total_revenue = (await cursor.fetchone())[0]

    # Đếm theo status
    cursor = await db.execute(
        """SELECT status, COUNT(*) as cnt
           FROM orders GROUP BY status"""
    )
    status_counts = {row[0]: row[1] for row in await cursor.fetchall()}

    # Đơn hôm nay (shift cả 2 vế sang VN time để so sánh đúng ngày VN)
    cursor = await db.execute(
        """SELECT COUNT(*) FROM orders
           WHERE date(created_at, '+7 hours') = date('now', '+7 hours')"""
    )
    today_orders = (await cursor.fetchone())[0]

    # Doanh thu hôm nay
    cursor = await db.execute(
        """SELECT COALESCE(SUM(amount), 0) FROM orders
           WHERE status = 'completed' AND date(created_at, '+7 hours') = date('now', '+7 hours')"""
    )
    today_revenue = (await cursor.fetchone())[0]

    return {
        "total_revenue": total_revenue,
        "status_counts": status_counts,
        "today_orders": today_orders,
        "today_revenue": today_revenue,
    }
