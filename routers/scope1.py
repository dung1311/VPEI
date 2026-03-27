from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from core.database import get_db
from core.security import decode_token, get_token_payload
from services.scope1_dashboard import Scope1DashboardService
from services.scope1_emission_source import DeviceCategoryService, ActivityDataService, DashboardService
from models.scope1 import FuelTypeEnum, DeviceTypeEnum, RecordStatusEnum
from schemas.scope1_emission_source import (
    DeviceCategoryCreate,
    DeviceCategoryResponse,
    DeviceCategoryUpdate,
    ActivityDataCreate,
    ActivityDataResponse,
    ActivityDataUpdate,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _actor_from_request(request: Request) -> str:
    payload = get_token_payload(request) or {}
    return payload.get("sub") or "system"


def _require_user_or_redirect(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        return decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp


# Dashboard page (Scope 1)
@router.get("/scope1", response_class=HTMLResponse)
@router.get("/scope1/", response_class=HTMLResponse)
def scope1_dashboard_page(request: Request, year: int = Query(None), month: int = Query(None), db: Session = Depends(get_db)):
    user_check = _require_user_or_redirect(request)
    if isinstance(user_check, RedirectResponse):
        return user_check
    current_user = user_check

    now = datetime.now()
    curr_year = year or now.year
    curr_month = month or now.month

    dashboard_data = Scope1DashboardService.get_dashboard_data(db, curr_year, curr_month)
    period_info = DashboardService.get_period_summary(db, curr_year, curr_month)

    return templates.TemplateResponse(
        "scope/scope_01_dashboard.html",
        {
            "request": request,
            "user": current_user,
            "current_year": curr_year,
            "current_month": curr_month,
            "status": period_info["status"].value if period_info["status"] else "Draft",
            "data": dashboard_data,
        },
    )


# Export dashboard Excel (keeps original path)
@router.get("/scope1/dashboard/export/excel")
def export_dashboard_excel(year: int, month: int, db: Session = Depends(get_db)):
    excel_file = Scope1DashboardService.export_excel(db, year, month)
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=VPEI_Scope1_{month}_{year}.xlsx"},
    )


# Emission source page (Scope 1)
@router.get("/scope1-emission-source", response_class=HTMLResponse)
@router.get("/scope1/emission-source", response_class=HTMLResponse)
def scope1_emission_source_page(request: Request, year: int = Query(None), month: int = Query(None), db: Session = Depends(get_db)):
    user_check = _require_user_or_redirect(request)
    if isinstance(user_check, RedirectResponse):
        return user_check
    current_user = user_check

    now = datetime.now()
    current_year = year if year is not None else now.year
    current_month = month if month is not None else now.month

    db_categories = DeviceCategoryService.get_all(db)
    categories_payload = []
    for cat in db_categories:
        total_ems = sum(
            act.total_co2e for act in getattr(cat, "activities", []) if act.period_year == current_year and act.period_month == current_month
        )
        categories_payload.append(
            {
                "id": cat.id,
                "name": cat.name,
                "device_type": cat.device_type,
                "fuel_type": cat.fuel_type,
                "count": getattr(cat, "total_quantity", None),
                "capacity": getattr(cat, "nominal_capacity", None),
                "total_emissions": f"{total_ems:,.1f}",
            }
        )

    db_activities = ActivityDataService.get_by_period(db, current_year, current_month)
    activities_payload = []
    for act in db_activities:
        activities_payload.append(
            {
                "id": act.id,
                "category_name": act.category.name if act.category else "N/A",
                "device_type": act.category.device_type if act.category else "N/A",
                "quantity": act.quantity,
                "power": act.recorded_power,
                "hours": act.operating_hours,
                "lf": act.load_factor,
                "total_co2": f"{act.total_co2e:,.1f}",
                "status": act.status,
            }
        )

    summary = DashboardService.get_period_summary(db, current_year, current_month)

    return templates.TemplateResponse(
        "scope/scope_01_emission_source.html",
        {
            "request": request,
            "user": current_user,
            "categories": categories_payload,
            "activities": activities_payload,
            "total_scope1_co2": f"{summary['total_co2e']:,.1f}",
            "status": summary['status'],
            "current_year": current_year,
            "current_month": current_month,
            "fuel_types": [f.value for f in FuelTypeEnum],
            "device_types": [d.value for d in DeviceTypeEnum],
        },
    )


"""
API endpoints for Scope 1 (mirrors previous routers/scope1_emission_source.py)
All paths follow the `/api/scope1/...` convention similar to scope2.
"""


@router.post("/api/scope1/activities/update-period-status")
def update_period_status(year: int, month: int, status: RecordStatusEnum, db: Session = Depends(get_db)):
    return ActivityDataService.update_period_status(db, year, month, status)


@router.post("/api/scope1/categories", response_model=DeviceCategoryResponse)
def create_category(payload: DeviceCategoryCreate, request: Request, db: Session = Depends(get_db)):
    return DeviceCategoryService.create(db, payload)


@router.put("/api/scope1/categories/{category_id}", response_model=DeviceCategoryResponse)
def update_category(category_id: int, payload: DeviceCategoryUpdate, request: Request, db: Session = Depends(get_db)):
    return DeviceCategoryService.update(db, category_id, payload)


@router.delete("/api/scope1/categories/{category_id}")
def delete_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    return DeviceCategoryService.delete(db, category_id)


@router.post("/api/scope1/activities", response_model=ActivityDataResponse)
def create_activity(payload: ActivityDataCreate, request: Request, db: Session = Depends(get_db)):
    return ActivityDataService.create(db, payload)


@router.post("/api/scope1/activities/import", tags=["Scope 1 - Activities"])
async def import_activities(
    request: Request,
    file: UploadFile = File(...),
    period_year: int = Form(...),
    period_month: int = Form(...),
    db: Session = Depends(get_db),
):
    return await ActivityDataService.import_from_excel(db, file, period_year, period_month)


@router.put("/api/scope1/activities/{activity_id}", response_model=ActivityDataResponse)
def update_activity(activity_id: int, payload: ActivityDataUpdate, request: Request, db: Session = Depends(get_db)):
    return ActivityDataService.update(db, activity_id, payload)


@router.delete("/api/scope1/activities/{activity_id}")
def delete_activity(activity_id: int, request: Request, db: Session = Depends(get_db)):
    return ActivityDataService.delete(db, activity_id)


@router.get("/api/scope1/dashboard/export-excel")
def api_export_dashboard_excel(year: int, month: int, db: Session = Depends(get_db)):
    excel_file = Scope1DashboardService.export_excel(db, year, month)
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=VPEI_Scope1_{month}_{year}.xlsx"},
    )
