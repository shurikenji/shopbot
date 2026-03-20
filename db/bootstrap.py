"""
db/bootstrap.py - Khởi tạo schema và migration cho database.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable

from db.database import get_db
from db.models import _CREATE_TABLES, _DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

_BEST_EFFORT_MIGRATIONS = [
    "ALTER TABLE api_servers ADD COLUMN quota_multiple REAL NOT NULL DEFAULT 1.0",
    "ALTER TABLE orders ADD COLUMN custom_quota INTEGER",
    "ALTER TABLE api_servers ADD COLUMN default_group TEXT",
    "ALTER TABLE products ADD COLUMN format_template TEXT",
    "ALTER TABLE products ADD COLUMN input_prompt TEXT",
    "ALTER TABLE api_servers ADD COLUMN api_type TEXT DEFAULT 'newapi'",
    "ALTER TABLE api_servers ADD COLUMN supports_multi_group INTEGER DEFAULT 0",
    "ALTER TABLE api_servers ADD COLUMN groups_cache TEXT",
    "ALTER TABLE api_servers ADD COLUMN groups_updated_at TEXT",
    "ALTER TABLE api_servers ADD COLUMN manual_groups TEXT",
    "ALTER TABLE api_servers ADD COLUMN auth_type TEXT DEFAULT 'header'",
    "ALTER TABLE api_servers ADD COLUMN auth_user_header TEXT",
    "ALTER TABLE api_servers ADD COLUMN auth_user_value TEXT",
    "ALTER TABLE api_servers ADD COLUMN auth_token TEXT",
    "ALTER TABLE api_servers ADD COLUMN auth_cookie TEXT",
    "ALTER TABLE api_servers ADD COLUMN custom_headers TEXT",
    "ALTER TABLE api_servers ADD COLUMN groups_endpoint TEXT",
    "ALTER TABLE api_servers ADD COLUMN import_spend_accrual_enabled INTEGER DEFAULT 0",
    "ALTER TABLE api_servers ADD COLUMN discount_stack_mode TEXT DEFAULT 'exclusive'",
    "ALTER TABLE api_servers ADD COLUMN discount_allowed_stack_types TEXT DEFAULT 'cashback'",
    "ALTER TABLE orders ADD COLUMN base_amount INTEGER",
    "ALTER TABLE orders ADD COLUMN discount_amount INTEGER DEFAULT 0",
    "ALTER TABLE orders ADD COLUMN cashback_amount INTEGER DEFAULT 0",
    "ALTER TABLE orders ADD COLUMN spend_credit_amount INTEGER DEFAULT 0",
    "ALTER TABLE orders ADD COLUMN pricing_version_id INTEGER",
    "ALTER TABLE orders ADD COLUMN applied_tier_id INTEGER",
    "ALTER TABLE orders ADD COLUMN pricing_snapshot TEXT",
    "ALTER TABLE orders ADD COLUMN promotion_snapshot TEXT",
    """UPDATE orders
       SET payment_method = 'wallet',
           updated_at = datetime('now')
       WHERE payment_method = 'qr'
         AND EXISTS (
             SELECT 1
             FROM wallet_transactions wt
             WHERE wt.user_id = orders.user_id
               AND wt.reference_id = orders.order_code
               AND wt.type = 'purchase'
               AND wt.amount = -orders.amount
         )""",
]


def _iter_statements(script: str) -> Iterable[str]:
    """Tách một khối SQL thành từng statement không rỗng."""
    for statement in script.split(";"):
        statement = statement.strip()
        if statement:
            yield statement


def _can_ignore_migration_error(error: Exception) -> bool:
    """Ignore only known idempotent migration errors."""
    if not isinstance(error, sqlite3.OperationalError):
        return False

    return "duplicate column name" in str(error).lower()


async def _apply_schema(db) -> None:
    """Tạo bảng và index từ DDL gốc."""
    for statement in _iter_statements(_CREATE_TABLES):
        await db.execute(statement)


async def _apply_best_effort_migrations(db) -> None:
    """Áp dụng migration an toàn cho DB cũ nếu cột chưa tồn tại."""
    for statement in _BEST_EFFORT_MIGRATIONS:
        try:
            await db.execute(statement)
        except Exception as exc:
            if _can_ignore_migration_error(exc):
                continue
            logger.warning("Database migration failed: %s", statement)
            raise


async def init_db() -> None:
    """Khởi tạo schema, migration và default settings."""
    db = await get_db()
    await _apply_schema(db)
    await _apply_best_effort_migrations(db)
    await db.executemany(
        "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)",
        _DEFAULT_SETTINGS,
    )
    await db.commit()
    logger.info("Database bootstrap complete.")
