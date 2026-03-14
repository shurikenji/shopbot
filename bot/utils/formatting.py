"""
bot/utils/formatting.py — Hàm format hiển thị cho bot messages.
Format tiền VNĐ, quota, mask API key, status emoji.
"""
from __future__ import annotations
import datetime


def format_vnd(amount: int) -> str:
    """
    Format số tiền VNĐ có dấu chấm phân cách hàng nghìn.
    Ví dụ: 31000 → '31.000₫', -50000 → '-50.000₫'
    """
    sign = "-" if amount < 0 else ""
    formatted = f"{abs(amount):,}".replace(",", ".")
    return f"{sign}{formatted}₫"


def format_quota(quota: int) -> str:
    """
    Format quota dễ đọc.
    Ví dụ: 1500000 → '1,500,000', 0 → '0'
    """
    return f"{quota:,}"


def format_dollar(amount: float) -> str:
    """
    Format dollar amount.
    Ví dụ: 10.0 → '$10.00', 0.5 → '$0.50'
    """
    return f"${amount:,.2f}"


def quota_to_dollar(quota: int, multiple: float = 1.0) -> str:
    """
    Chuyển đổi quota → số dư dollar theo công thức:
    balance = quota / 500000 / multiple
    Ví dụ: quota=500000, multiple=1.0 → '$1.00'
            quota=1000000, multiple=2.0 → '$1.00'
    """
    if multiple <= 0:
        multiple = 1.0
    dollar = quota / 500000 / multiple
    return f"${dollar:,.2f}"


def mask_api_key(key: str) -> str:
    """
    Mask API key chỉ hiện 8 ký tự đầu và 4 ký tự cuối.
    Ví dụ: 'sk-abcdefghijklmn' → 'sk-abcde...klmn'
    """
    if len(key) <= 12:
        return key
    return f"{key[:8]}...{key[-4:]}"


def status_emoji(status: str) -> str:
    """Trả về emoji tương ứng với trạng thái đơn hàng."""
    mapping = {
        "pending": "⏳",
        "paid": "💰",
        "processing": "⚙️",
        "completed": "✅",
        "failed": "❌",
        "expired": "⌛",
        "refunded": "↩️",
        "cancelled": "🚫",
    }
    return mapping.get(status, "❓")


def status_text_vi(status: str) -> str:
    """Trả về tên trạng thái tiếng Việt."""
    mapping = {
        "pending": "Chờ thanh toán",
        "paid": "Đã thanh toán",
        "processing": "Đang xử lý",
        "completed": "Hoàn thành",
        "failed": "Thất bại",
        "expired": "Hết hạn",
        "refunded": "Đã hoàn tiền",
        "cancelled": "Đã hủy",
    }
    return mapping.get(status, status)


def payment_method_text(method: str) -> str:
    """Trả về tên phương thức thanh toán tiếng Việt."""
    mapping = {
        "qr": "🏦 Chuyển khoản QR",
        "wallet": "👛 Ví nội bộ",
    }
    return mapping.get(method, method)


def truncate_text(text: str, max_len: int = 50) -> str:
    """Cắt bớt text nếu quá dài, thêm '…'."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_time_vn(utc_time_str: str) -> str:
    """
    Chuyển đổi chuỗi UTC thời gian từ database 'YYYY-MM-DD HH:MM:SS'
    thành chuỗi hiển thị theo giờ Việt Nam (GMT+7).
    """
    if not utc_time_str:
        return ""
    try:
        # Cắt lấy 19 ký tự đầu để tránh lỗi millis/microseconds '2026-03-11 07:40:32'
        base_str = str(utc_time_str)[:19].replace('T', ' ')
        dt = datetime.datetime.strptime(base_str, "%Y-%m-%d %H:%M:%S")
        vn_dt = dt + datetime.timedelta(hours=7)
        return vn_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # Fallback lại input gốc nếu lỗi format
        return str(utc_time_str)[:19]
