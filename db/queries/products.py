"""
db/queries/products.py — CRUD operations cho bảng products.
"""
from __future__ import annotations

from typing import Optional

from db.database import get_db


async def get_active_products_by_category(
    category_id: int,
    server_id: Optional[int] = None,
    product_type: Optional[str] = None,
) -> list[dict]:
    """Lấy sản phẩm active theo danh mục, optional filter server + type."""
    db = await get_db()
    query = """
        SELECT p.*,
               (SELECT COUNT(id) FROM account_stocks WHERE product_id = p.id AND is_sold = 0) as real_stock
        FROM products p
        WHERE p.category_id = ? AND p.is_active = 1
    """
    params: list = [category_id]

    if server_id is not None:
        query += " AND p.server_id = ?"
        params.append(server_id)
    if product_type is not None:
        query += " AND p.product_type = ?"
        params.append(product_type)

    query += " ORDER BY p.sort_order ASC, p.id ASC"
    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    
    result = []
    for r in rows:
        d = dict(r)
        if d.get("product_type") == "account_stocked":
            d["stock"] = d.get("real_stock", 0)
        result.append(d)
    return result


async def get_product_by_id(product_id: int) -> Optional[dict]:
    """Lấy sản phẩm theo ID."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT p.*,
               (SELECT COUNT(id) FROM account_stocks WHERE product_id = p.id AND is_sold = 0) as real_stock
        FROM products p
        WHERE p.id = ?
        """,
        (product_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("product_type") == "account_stocked":
        d["stock"] = d.get("real_stock", 0)
    return d


async def get_all_products(
    offset: int = 0,
    limit: int = 50,
    category_id: Optional[int] = None,
    server_id: Optional[int] = None,
) -> list[dict]:
    """Lấy tất cả sản phẩm (admin, phân trang)."""
    db = await get_db()
    query = """
        SELECT p.*,
               (SELECT COUNT(id) FROM account_stocks WHERE product_id = p.id AND is_sold = 0) as real_stock
        FROM products p
        WHERE 1=1
    """
    params: list = []

    if category_id is not None:
        query += " AND p.category_id = ?"
        params.append(category_id)
    if server_id is not None:
        query += " AND p.server_id = ?"
        params.append(server_id)

    query += " ORDER BY p.sort_order ASC, p.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    
    result = []
    for r in rows:
        d = dict(r)
        if d.get("product_type") == "account_stocked":
            d["stock"] = d.get("real_stock", 0)
        result.append(d)
    return result


async def count_products(
    category_id: Optional[int] = None,
    server_id: Optional[int] = None,
) -> int:
    """Đếm tổng sản phẩm."""
    db = await get_db()
    query = "SELECT COUNT(*) FROM products WHERE 1=1"
    params: list = []

    if category_id is not None:
        query += " AND category_id = ?"
        params.append(category_id)
    if server_id is not None:
        query += " AND server_id = ?"
        params.append(server_id)

    cursor = await db.execute(query, tuple(params))
    row = await cursor.fetchone()
    return row[0] if row else 0


async def create_product(
    category_id: int,
    name: str,
    price_vnd: int,
    product_type: str,
    server_id: Optional[int] = None,
    description: Optional[str] = None,
    quota_amount: int = 0,
    dollar_amount: float = 0.0,
    group_name: Optional[str] = None,
    delivery_type: str = "auto",
    delivery_data: Optional[str] = None,
    stock: int = -1,
    sort_order: int = 0,
    meta_json: Optional[str] = None,
    format_template: Optional[str] = None,
    input_prompt: Optional[str] = None,
) -> int:
    """Tạo sản phẩm mới, trả về ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO products
           (category_id, server_id, name, description, price_vnd, product_type,
            quota_amount, dollar_amount, group_name, delivery_type, delivery_data,
            stock, sort_order, meta_json, format_template, input_prompt)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            category_id, server_id, name, description, price_vnd, product_type,
            quota_amount, dollar_amount, group_name, delivery_type, delivery_data,
            stock, sort_order, meta_json, format_template, input_prompt,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def update_product(product_id: int, **kwargs) -> None:
    """Cập nhật sản phẩm — chỉ update các field được truyền vào."""
    if not kwargs:
        return

    db = await get_db()
    allowed_fields = {
        "category_id", "server_id", "name", "description", "price_vnd",
        "product_type", "quota_amount", "dollar_amount", "group_name",
        "delivery_type", "delivery_data", "stock", "is_active",
        "sort_order", "meta_json", "format_template", "input_prompt",
    }

    fields = []
    values = []
    for key, val in kwargs.items():
        if key in allowed_fields:
            fields.append(f"{key} = ?")
            values.append(val)

    if not fields:
        return

    fields.append("updated_at = datetime('now', '+7 hours')")
    values.append(product_id)

    query = f"UPDATE products SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, tuple(values))
    await db.commit()


async def delete_product(product_id: int) -> None:
    """Xóa sản phẩm."""
    db = await get_db()
    await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    await db.commit()


async def get_product_delete_dependencies(product_id: int) -> dict:
    """Äáº¿m cÃ¡c báº£n ghi Ä‘ang tham chiáº¿u tá»›i sáº£n pháº©m."""
    db = await get_db()

    cursor = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE product_id = ?",
        (product_id,),
    )
    orders_count = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT COUNT(*) FROM account_stocks WHERE product_id = ?",
        (product_id,),
    )
    account_stocks_count = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT COUNT(*) FROM chatgpt_accounts WHERE product_id = ?",
        (product_id,),
    )
    legacy_accounts_count = (await cursor.fetchone())[0]

    return {
        "orders": orders_count,
        "account_stocks": account_stocks_count,
        "chatgpt_accounts": legacy_accounts_count,
        "total": orders_count + account_stocks_count + legacy_accounts_count,
    }


async def decrement_stock(product_id: int) -> bool:
    """
    Giảm stock 1 đơn vị. Trả về True nếu thành công.
    Stock = -1 nghĩa là unlimited, không giảm.
    """
    db = await get_db()
    product = await get_product_by_id(product_id)
    if not product:
        return False

    stock = product["stock"]
    if stock == -1:
        # Unlimited
        return True
    if stock <= 0:
        return False

    await db.execute(
        "UPDATE products SET stock = stock - 1, updated_at = datetime('now', '+7 hours') WHERE id = ? AND stock > 0",
        (product_id,),
    )
    await db.commit()
    return True
