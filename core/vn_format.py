"""Định dạng ngày giờ hiển thị chuẩn VN: dd/mm/yyyy hh:mm"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional, Union

VN_DATETIME_FMT = "%d/%m/%Y %H:%M"


def format_vn_datetime(value: Optional[Union[datetime, date]]) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime(VN_DATETIME_FMT)
    return datetime.combine(value, time.min).strftime(VN_DATETIME_FMT)


def format_vn_end_of_day(value: Optional[date]) -> str:
    if value is None:
        return "N/A"
    return datetime.combine(value, time(23, 59)).strftime(VN_DATETIME_FMT)


def journey_type_label_vn(journey_type: Any) -> str:
    """Scope 3 xe container: both / export / import → tiếng Việt."""
    if journey_type is None:
        return ""
    raw = getattr(journey_type, "value", journey_type)
    key = str(raw).strip().lower()
    return {
        "both": "Xuất và nhập",
        "export": "Xuất",
        "import": "Nhập",
    }.get(key, str(raw))


def parse_vn_display_datetime(s: str) -> datetime:
    """Parse chuỗi đã format hiển thị (có hoặc không giây) — dùng sort log."""
    text = (s or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min
