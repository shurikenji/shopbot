"""
bot/utils/time_utils.py — Utility tập trung quản lý thời gian.

Quy tắc vàng: Database LUÔN lưu UTC.
Chỉ cộng +7 giờ ở tầng hiển thị (UI) thông qua format_time_vn().
"""
from __future__ import annotations
from datetime import datetime


def get_now_vn() -> datetime:
    """
    Trả về datetime UTC hiện tại — dùng cho mọi logic backend
    (tạo đơn, tính expired_at, ghi log,...).

    ĐÃ REFACTOR: Trước đây trả UTC+7 gây xung đột với DB (lưu UTC).
    Tên hàm giữ nguyên để không phải sửa hàng chục file import.
    """
    return datetime.utcnow()
