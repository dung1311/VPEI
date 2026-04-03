# routers/scope1.py
from fastapi import APIRouter, Request, Depends, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from core.database import get_db
from core.security import decode_token
from services import scope1 as scope1_services
from schemas.device import DeviceCategoryCreate, DeviceCategoryUpdate, ActivityDataCreate, ActivityDataUpdate
from models.device import RecordStatusEnum, DeviceTypeEnum, FuelTypeEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _resolve_scope1_months(month: Optional[int], quarter: Optional[int]) -> List[int]:
    if month is not None:
        return [month]
    if quarter is not None:
        q = int(quarter)
        return list(range((q - 1) * 3 + 1, q * 3 + 1))
    return list(range(1, 13))


def _scope1_period_ctx(y: int, month: Optional[int], quarter: Optional[int], months: List[int]) -> dict:
    return {
        "year": y,
        "month": month,
        "quarter": quarter,
        "activity_month": min(months),
    }


# --- UI PAGES ---
@router.get("/scope1", response_class=HTMLResponse)
async def scope1_dashboard_page(
    request: Request,
    year: int = Query(None),
    month: int = Query(None),
    quarter: int = Query(None),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    y = year or now.year
    months = _resolve_scope1_months(month, quarter)
    dashboard = scope1_services.DashboardService.get_dashboard_data_for_months(db, y, months)

    return templates.TemplateResponse("scope/scope_01.html", {
        "request": request,
        "dashboard_json": dashboard,
        "current_year": y,
        "current_month": month if month is not None else min(months),
        "period_ctx": _scope1_period_ctx(y, month, quarter, months),
    })


@router.get("/scope1/emission-source", response_class=HTMLResponse)
async def scope1_emission_source_page(
    request: Request,
    year: int = Query(None),
    month: int = Query(None),
    quarter: int = Query(None),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    y = year or now.year
    months = _resolve_scope1_months(month, quarter)

    cats = scope1_services.DeviceCategoryService.get_all(db)
    activities = []
    for mo in months:
        activities.extend(scope1_services.ActivityDataService.get_by_period(db, y, mo))

    categories_for_ui = []
    for c in cats:
        total_em = sum(a.total_co2e for a in activities if a.category_id == c.id)
        categories_for_ui.append({
            "id": c.id, "name": c.name, "device_type": c.device_type.value,
            "fuel_type": c.fuel_type.value, "count": c.total_quantity,
            "capacity": c.nominal_capacity, "total_emissions": total_em,
        })

    acts_ui = [{
        "id": a.id, "device_type": a.category.device_type.value,
        "quantity": a.quantity, "power": a.recorded_power,
        "hours": a.operating_hours, "lf": a.load_factor, "total_co": a.total_co2e,
    } for a in activities]

    summary = scope1_services.DashboardService.get_dashboard_data_for_months(db, y, months)

    # [FIXED] Trích xuất status an toàn hơn
    status_str = summary["kpis"]["status"] if "status" in summary.get("kpis", {}) else "Draft"

    act_m = min(months)
    period_ctx = {**_scope1_period_ctx(y, month, quarter, months), "status": status_str}

    return templates.TemplateResponse("scope/scope_01_emission_source.html", {
        "request": request,
        "categories": categories_for_ui,
        "activities": acts_ui,
        "device_types": [d.value for d in DeviceTypeEnum],
        "fuel_types": [f.value for f in FuelTypeEnum],
        "current_year": y,
        "current_month": act_m,
        "period_ctx": period_ctx,
        "status": status_str,
        "total_scope1_co2": summary["kpis"]["total_co2e"],
        "trend_data": summary["line_chart"]
    })


# --- API ENDPOINTS ---
@router.post("/scope1/categories")
async def create_category(payload: DeviceCategoryCreate, db: Session = Depends(get_db)):
    return scope1_services.DeviceCategoryService.create(db, payload)

@router.put("/scope1/categories/{category_id}")
async def update_category(category_id: int, payload: DeviceCategoryUpdate, db: Session = Depends(get_db)):
    return scope1_services.DeviceCategoryService.update(db, category_id, payload)

@router.delete("/scope1/categories/{category_id}")
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    return scope1_services.DeviceCategoryService.delete(db, category_id)

@router.post("/scope1/activities")
async def create_activity(payload: ActivityDataCreate, db: Session = Depends(get_db)):
    return scope1_services.ActivityDataService.create(db, payload)

@router.put("/scope1/activities/{activity_id}")
async def update_activity(activity_id: int, payload: ActivityDataUpdate, db: Session = Depends(get_db)):
    return scope1_services.ActivityDataService.update(db, activity_id, payload)

@router.delete("/scope1/activities/{activity_id}")
async def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    return scope1_services.ActivityDataService.delete(db, activity_id)

@router.post("/scope1/activities/import")
async def import_activities(file: UploadFile = File(...), period_year: int = Query(...), period_month: int = Query(...), db: Session = Depends(get_db)):
    return await scope1_services.ActivityDataService.import_from_excel(db, file, period_year, period_month)

@router.post("/scope1/activities/update-period-status")
async def update_period_status(year: int = Query(...), month: int = Query(...), status: str = Query(...), db: Session = Depends(get_db)):
    try:
        enum_status = RecordStatusEnum(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")
    return scope1_services.ActivityDataService.update_period_status(db, year, month, enum_status)

@router.get("/api/scope1/dashboard/export-excel")
async def api_export_dashboard(
    year: int = Query(...),
    month: int = Query(None),
    quarter: int = Query(None),
    db: Session = Depends(get_db),
):
    months = _resolve_scope1_months(month, quarter)
    payload = scope1_services.DashboardService.export_excel(db, year, months)
    if len(months) == 1:
        tag = months[0]
    elif len(months) == 3:
        tag = f"Q{((months[0] - 1) // 3) + 1}"
    else:
        tag = "Y"
    return StreamingResponse(
        iter([payload.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=scope1_dashboard_{tag}_{year}.xlsx"}
    )