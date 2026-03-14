"""
db/database.py — aiosqlite singleton connection manager.
Dùng một connection duy nhất cho toàn bộ application (async-safe).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

# Singleton connection
_db: Optional[aiosqlite.Connection] = None
_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    """
    Lấy singleton database connection.
    Tạo connection mới nếu chưa có hoặc connection cũ đã đóng.
    """
    global _db

    if _db is not None:
        try:
            # Quick check: connection vẫn sống
            await _db.execute("SELECT 1")
            return _db
        except Exception:
            _db = None

    async with _lock:
        # Double-check sau khi acquire lock
        if _db is not None:
            try:
                await _db.execute("SELECT 1")
                return _db
            except Exception:
                _db = None

        from bot.config import settings

        db_path = Path(settings.db_path)
        logger.info("Opening database: %s", db_path)

        _db = await aiosqlite.connect(str(db_path))
        # Enable WAL mode cho concurrent reads tốt hơn
        await _db.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        await _db.execute("PRAGMA foreign_keys=ON")
        # Row factory: trả về Row objects có thể truy cập bằng tên cột
        _db.row_factory = aiosqlite.Row

        return _db


async def close_db() -> None:
    """Đóng database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("Database connection closed.")
