# routers/scope1.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.security import decode_token   # giống hệt pattern dashboard

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ── Helper: format số có dấu phẩy ─────────────
def fmt(value) -> str:
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


# ── Dữ liệu mẫu ───────────────────────────────
SAMPLE_DEVICES = [
    {"id": "RS-01", "fuel_type": "Dầu DO", "consumption": 145000, "co2e": 1285, "percentage": 12.08},
    {"id": "RS-02", "fuel_type": "Dầu DO", "consumption": 145000, "co2e":  285, "percentage": 10.00},
    {"id": "RS-03", "fuel_type": "Dầu FO", "consumption":  85000, "co2e":  285, "percentage":  9.83},
    {"id": "RS-04", "fuel_type": "Dầu DO", "consumption":  72000, "co2e":  242, "percentage":  8.45},
    {"id": "RS-05", "fuel_type": "Dầu DO", "consumption":  58000, "co2e":  196, "percentage":  7.20},
    {"id": "RS-06", "fuel_type": "Dầu DO", "consumption":  48000, "co2e":  162, "percentage":  5.90},
    {"id": "RS-07", "fuel_type": "Dầu DO", "consumption":  42000, "co2e":  141, "percentage":  5.10},
    {"id": "RS-08", "fuel_type": "Dầu DO", "consumption":  30000, "co2e":   98, "percentage":  3.62},
]

MONTHS = [{"value": i, "label": f"Tháng {i:02d}"} for i in range(1, 13)]
YEARS  = [2026, 2025, 2024]


# ── Route: GET /scope1?year=2026&month=1 ───────
@router.get("/scope1", response_class=HTMLResponse)
async def scope1_page(request: Request, year: int = 2026, month: int = 1):

    # Auth — giống hệt dashboard
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    # Lấy dữ liệu (thay bằng DB query thực tế)
    raw_devices = get_devices(year, month)

    # Tính KPI
    total_fuel_raw = sum(d["consumption"] for d in raw_devices)
    total_co2e_raw = sum(d["co2e"]        for d in raw_devices)
    top_device     = max(raw_devices, key=lambda d: d["co2e"]) if raw_devices else {}
    change_pct     = 6.5    # % — tính từ DB thực tế
    is_increase    = True   # True = tăng (đỏ) | False = giảm (xanh)

    # Format số ở Python trước khi truyền vào template
    devices_fmt = [
        {
            "id":         d["id"],
            "fuel_type":  d["fuel_type"],
            "consumption": fmt(d["consumption"]),
            "co2e":        fmt(d["co2e"]),
            "percentage":  d["percentage"],   # float — format bằng "%.2f" trong template
        }
        for d in raw_devices
    ]

    return templates.TemplateResponse(
        "scope/scope_01.html",
        {
            "request": request,
            "user":    current_user,   # ← truyền giống dashboard, base.html dùng để hiện navbar

            # Filters
            "years":          YEARS,
            "months":         MONTHS,
            "selected_year":  year,
            "selected_month": month,

            # KPI (đã format thành string)
            "total_fuel":         fmt(total_fuel_raw),
            "total_co2e":         fmt(total_co2e_raw),
            "top_device_name":    top_device.get("id", "-"),
            "top_device_co2e":    fmt(top_device.get("co2e", 0)),
            "change_percent":     f"{abs(change_pct):.1f}%",
            "change_is_increase": is_increase,

            # Table
            "devices": devices_fmt,

            # Charts (list số nguyên — tojson dùng trực tiếp)
            "chart_bar_labels":    [d["id"]   for d in raw_devices],
            "chart_bar_data":      [d["co2e"] for d in raw_devices],
            "chart_trend_data_12": [72, 100, 110, 75, 120, 125, 128, 148, 130, 132, 119, 163],
            "chart_trend_data_6":  [128, 148, 130, 132, 119, 163],
        },
    )


def get_devices(year: int, month: int) -> list[dict]:
    # TODO: thay bằng SQLAlchemy / Tortoise query thực tế
    return SAMPLE_DEVICES