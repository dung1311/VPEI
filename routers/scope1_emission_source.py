# routers/scope1_emssion_source.py
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from core.database import get_db
from models.device import DeviceCategory, ActivityData, FuelTypeEnum, DeviceTypeEnum
from services.device import DeviceCategoryService, ActivityDataService, DashboardService
from schemas.device import DeviceCategoryCreate, DeviceCategoryResponse, ActivityDataCreate, ActivityDataResponse, DeviceCategoryUpdate, ActivityDataUpdate

router = APIRouter(prefix="/scope1", tags=["Scope 1"])
templates = Jinja2Templates(directory="templates")

@router.get("/scope1-emission-source", response_class=HTMLResponse, include_in_schema=False)
def render_scope1_dashboard(request: Request, year: int = 2026, month: int = 2, db: Session = Depends(get_db)):
    db_categories = db.query(DeviceCategory).all()
    cat_data = []
    
    # Render các Card
    for cat in db_categories:
        emissions = db.query(func.sum(ActivityData.total_co2e)).filter(
            ActivityData.category_id == cat.id,
            ActivityData.period_year == year,
            ActivityData.period_month == month
        ).scalar() or 0.0
            
        cat_data.append({
            "id": cat.id,
            "name": cat.name,
            "device_type": cat.device_type, # THÊM
            "fuel_type": cat.fuel_type,     # THÊM
            "count": cat.total_quantity,
            "capacity": cat.nominal_capacity, # THÊM
            "total_emissions": f"{emissions:,.1f}"
        })

    # Render Bảng nhập liệu
    db_activities = db.query(ActivityData).filter(
        ActivityData.period_year == year,
        ActivityData.period_month == month

    ).all()
    
    act_data = []
    for act in db_activities:
        act_data.append({
            "id": act.id,
            "device_type": act.category.device_type if act.category else "Unknown",
            "quantity": act.quantity,
            "power": act.recorded_power,
            "hours": act.operating_hours,
            "lf": act.load_factor,
            "total_co2": f"{act.total_co2e:,.1f}"
        })

    total_summary = DashboardService.get_summary(db, year, month)
    total_co2 = f"{total_summary['total_co2e']:,.1f}"

    return templates.TemplateResponse(
        "scope/scope_01_emission_source.html",
        {
            "request": request,
            "current_year": year,
            "current_month": f"{month:02d}",
            "categories": cat_data,
            "activities": act_data,
            "total_scope1_co2": total_co2,
            "fuel_types": [f.value for f in FuelTypeEnum],
            "device_types": [d.value for d in DeviceTypeEnum]
        }
    )

@router.post("/categories", response_model=DeviceCategoryResponse)
def create_category(payload: DeviceCategoryCreate, db: Session = Depends(get_db)):
    return DeviceCategoryService.create(db, payload)

@router.put("/categories/{category_id}", response_model=DeviceCategoryResponse)
def update_category(category_id: int, payload: DeviceCategoryUpdate, db: Session = Depends(get_db)):
    return DeviceCategoryService.update(db, category_id, payload)


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    return DeviceCategoryService.delete(db, category_id)

@router.post("/activities", response_model=ActivityDataResponse)
def create_activity(payload: ActivityDataCreate, db: Session = Depends(get_db)):
    return ActivityDataService.create(db, payload)

@router.post("/activities/import", tags=["Scope 1 - Activities"])
async def import_activities(
    file: UploadFile = File(...),
    period_year: int = Form(...),
    period_month: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    Endpoint nhận file Excel và import dữ liệu hoạt động.
    Cho phép ghi đè Power (kW) từ file Excel.
    """
    return await ActivityDataService.import_from_excel(
        db, file, period_year, period_month
    )

@router.put("/activities/{activity_id}", response_model=ActivityDataResponse)
def update_activity(activity_id: int, payload: ActivityDataUpdate, db: Session = Depends(get_db)):
    return ActivityDataService.update(db, activity_id, payload)

@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    return ActivityDataService.delete(db, activity_id)


    