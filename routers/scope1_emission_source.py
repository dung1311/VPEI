# routers/scope1_emssion_source.py
import datetime

from datetime import datetime

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fastapi import APIRouter, Depends, Request, Query

from core.database import get_db
from models.scope1 import DeviceCategory, ActivityData, FuelTypeEnum, DeviceTypeEnum, RecordStatusEnum
from services.scope1_emission_source import DeviceCategoryService, ActivityDataService, DashboardService
from schemas.scope1_emission_source import DeviceCategoryCreate, DeviceCategoryResponse, ActivityDataCreate, ActivityDataResponse, DeviceCategoryUpdate, ActivityDataUpdate

router = APIRouter(prefix="/scope1", tags=["Scope 1"])
templates = Jinja2Templates(directory="templates")

@router.get("/scope1-emission-source", response_class=HTMLResponse)
def render_scope1_dashboard(
    request: Request,
    year: int = Query(None),
    month: int = Query(None),
    db: Session = Depends(get_db)
):
    # 1. Xác định thời gian lọc (mặc định là tháng/năm hiện tại nếu không có tham số)
    now = datetime.now()
    current_year = year if year is not None else now.year
    current_month = month if month is not None else now.month

    # 2. Lấy dữ liệu danh mục (Categories) và chuyển sang Dictionary để tránh lỗi JSON
    db_categories = DeviceCategoryService.get_all(db)
    categories_payload = []
    
    for cat in db_categories:
        # Tính tổng phát thải của nhóm này trong kỳ đang chọn (Nếu backend có quan hệ activities)
        # Nếu chưa có logic tính lẻ, bạn có thể để mặc định "0.0"
        total_ems = sum(act.total_co2e for act in cat.activities 
                        if act.period_year == current_year and act.period_month == current_month)
        
        categories_payload.append({
            "id": cat.id,
            "name": cat.name,
            "device_type": cat.device_type,
            "fuel_type": cat.fuel_type,
            "count": cat.total_quantity,
            "capacity": cat.nominal_capacity,
            "total_emissions": f"{total_ems:,.1f}"
        })

    # 3. Lấy dữ liệu hoạt động (Activities) đã lọc theo thời gian
    db_activities = ActivityDataService.get_by_period(db, current_year, current_month)
    activities_payload = []
    
    for act in db_activities:
        activities_payload.append({
            "id": act.id,
            "category_name": act.category.name if act.category else "N/A",
            "device_type": act.category.device_type if act.category else "N/A",
            "quantity": act.quantity,
            "power": act.recorded_power,
            "hours": act.operating_hours,
            "lf": act.load_factor,
            "total_co2": f"{act.total_co2e:,.1f}",
            "status": act.status
        })

    # 4. Lấy tóm tắt tổng quát của kỳ (Tổng CO2 toàn hệ thống, Trạng thái chung)
    summary = DashboardService.get_period_summary(db, current_year, current_month)

    # 5. Trả về giao diện kèm toàn bộ dữ liệu đã xử lý
    return templates.TemplateResponse(
        "scope/scope_01_emission_source.html",
        {
            "request": request,
            "categories": categories_payload, # Đã là list dict, an toàn cho | tojson
            "activities": activities_payload,
            "total_scope1_co2": f"{summary['total_co2e']:,.1f}",
            "status": summary['status'],
            "current_year": current_year,
            "current_month": current_month,
            "fuel_types": [f.value for f in FuelTypeEnum],
            "device_types": [d.value for d in DeviceTypeEnum]
        }
    )

@router.post("/activities/update-period-status")
def update_period_status(year: int, month: int, status: RecordStatusEnum, db: Session = Depends(get_db)):
    return ActivityDataService.update_period_status(db, year, month, status)

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


    