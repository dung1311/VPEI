# routers/dashboard.py
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Set

from core.database import get_db
from core.security import decode_token

from services import electrical_items_service
from services import equipment_service
from services import scope1 as scope1_services
from services.scope3_period_service import compute_scope3_period

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _month_filter_set(month: Optional[int], quarter: Optional[int]) -> Optional[Set[int]]:
    if month is not None:
        return {month}
    if quarter is not None:
        q = int(quarter)
        return set(range((q - 1) * 3 + 1, q * 3 + 1))
    return None


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    year: Optional[int] = Query(None),
    quarter: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    now = datetime.now()
    current_year = year or now.year
    mf = _month_filter_set(month, quarter)
    if month is not None:
        period_label = f"Tháng {month}/{current_year}"
    elif quarter is not None:
        period_label = f"Quý {quarter}/{current_year}"
    else:
        period_label = f"Năm {current_year}"

    def parse_date(dt_val):
        if not dt_val:
            return None
        if isinstance(dt_val, datetime):
            return dt_val
        if isinstance(dt_val, str):
            try:
                return datetime.fromisoformat(dt_val.replace("Z", "+00:00").split(".")[0])
            except ValueError:
                return None
        return None

    s1_trend = [0.0] * 12
    s1_total = 0.0
    try:
        # Tier 1 Equipment emissions
        s1_summary = equipment_service.summary_by_scope(db, 1, year=current_year, month=month, quarter=quarter)
        t1_total = float(s1_summary["total_co2e"] or 0.0)
        t1_trend = [float(v) for v in s1_summary["monthly_totals"]]
        
        # Emission Source (ActivityData) emissions
        if month is not None:
            months = [month]
        elif quarter is not None:
            q = int(quarter)
            months = list(range((q - 1) * 3 + 1, q * 3 + 1))
        else:
            months = list(range(1, 13))
            
        act_summary = scope1_services.DashboardService.get_dashboard_data_for_months(db, current_year, months)
        act_total = float(act_summary["kpis"]["total_co2e"] or 0.0)
        act_trend = [float(v) for v in act_summary["line_chart"]["values"]]

        s1_total = t1_total + act_total
        s1_trend = [a + b for a, b in zip(t1_trend, act_trend)]
    except Exception as e:
        print("Lỗi Dashboard Scope 1:", e)

    s2_trend = [0.0] * 12
    s2_total = 0.0
    try:
        s2_items = electrical_items_service.get_scope2_categories(db)
        GRID_EF = 0.0006235

        for item in s2_items:
            kwh = float(item.get("kwh", 0.0) if isinstance(item, dict) else getattr(item, "kwh", 0.0))
            if kwh <= 0:
                continue

            raw_date = item.get("entry_date", None) if isinstance(item, dict) else getattr(item, "entry_date", None)
            dt = parse_date(raw_date)
            if not (dt and dt.year == current_year):
                continue
            if mf is not None and dt.month not in mf:
                continue

            val_co2 = kwh * GRID_EF
            s2_total += val_co2
            s2_trend[dt.month - 1] += val_co2

    except Exception as e:
        print("Lỗi Scope 2:", e)

    s3_trend = [0.0] * 12
    s3_total = 0.0
    total_trips = 0
    try:
        s3_payload = compute_scope3_period(db, current_year, month, quarter)
        s3_trend = [float(a) for a in s3_payload["trend_monthly"]]
        s3_total = float(s3_payload["total_co2e"])
        total_trips = s3_payload["record_count"]
    except Exception as e:
        print("Lỗi Scope 3:", e)

    equip_list = []
    if s1_total > 0:
        equip_list.append({"label": "Scope 1", "value": s1_total})
    if s2_total > 0:
        equip_list.append({"label": "Scope 2", "value": s2_total})
    if s3_total > 0:
        equip_list.append({"label": "Scope 3", "value": s3_total})

    top_labels = [x["label"] for x in equip_list] or ["Chưa có dữ liệu"]
    top_values = [x["value"] for x in equip_list] or [1]

    def to_quarters(t):
        return [sum(t[0:3]), sum(t[3:6]), sum(t[6:9]), sum(t[9:12]), sum(t)]

    data = {
        "total_emissions": s1_total + s2_total + s3_total,
        "scope1_total": s1_total,
        "scope2_total": s2_total,
        "scope3_total": s3_total,
        "total_trips": total_trips,
        "current_year": current_year,
        "period_label": period_label,
        "last_updated": now.strftime("%d/%m/%Y %H:%M"),
        "trend": {
            "months": ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12"],
            "scope1": s1_trend,
            "scope2": s2_trend,
            "scope3": s3_trend,
        },
        "quarterly": {
            "labels": ["Quý 1", "Quý 2", "Quý 3", "Quý 4", "Cả Năm (YTD)"],
            "scope1": to_quarters(s1_trend),
            "scope2": to_quarters(s2_trend),
            "scope3": to_quarters(s3_trend),
        },
        "top_equipment": {"labels": top_labels, "values": top_values},
    }

    return templates.TemplateResponse(
        "dashboard/dashboard.html",
        {"request": request, "user": current_user, "data": data},
    )
