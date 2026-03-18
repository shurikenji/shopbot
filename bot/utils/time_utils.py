"""
bot/utils/time_utils.py — Utility tập trung quản lý thời gian.

Quy tắc vàng: Database luôn lưu UTC.
Chỉ cộng +7 giờ ở tầng hiển thị (UI) thông qua format_time_vn().
"""
from __future__ import annotations

from datetime import datetime


def get_now_vn() -> datetime:
    """
    Trả về datetime UTC hiện tại cho toàn bộ logic backend.

    Hàm vẫn giữ tên cũ để tránh phải sửa hàng chục import hiện có.
    """
    return datetime.utcnow()
