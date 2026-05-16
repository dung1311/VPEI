# routers/scope1.py
from fastapi import APIRouter, Request, Depends, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class BulkDeleteRequest(BaseModel):
    ids: List[int]


from core.database import get_db
from core.security import decode_token
from services import scope1 as scope1_services
from services import equipment_service
from schemas.device import DeviceCreate, DeviceUpdate, ActivityDataCreate, ActivityDataUpdate
from schemas.emission_source import EquipmentCreate, EquipmentUpdate, EquipmentRecordCreate, ScopeCategoryCreate, ScopeCategoryUpdate
from models.device import DeviceTypeEnum, FuelTypeEnum
from models.emission_source import CalculationMethodEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _user_from_request(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return decode_token(token)
    except Exception:
        return None


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


def _scope1_emission_source_context(db: Session, y: int, month: Optional[int], quarter: Optional[int], months: List[int]) -> dict:
    devices = scope1_services.DeviceService.get_all(db)
    activities = scope1_services.ActivityDataService.get_by_record_time(db, y, months)

    device_rows = []
    for device in devices:
        device_activities = [act for act in activities if act.device_id == device.id]
        device_rows.append({
            "id": device.id,
            "name": device.name,
            "device_type": device.device_type.value if device.device_type else "",
            "fuel_type": device.fuel_type.value if device.fuel_type else "",
            "capacity": device.nominal_capacity,
            "total_emissions": sum(float(act.total_co2e or 0.0) for act in device_activities),
        })

    activity_rows = []
    for act in activities:
        device = next((item for item in devices if item.id == act.device_id), None)
        activity_rows.append({
            "id": act.id,
            "device_id": act.device_id,
            "device_name": device.name if device else act.device_id,
            "device_type": act.device_type.value if act.device_type else "",
            "power": act.recorded_power,
            "hours": act.operating_hours,
            "lf": float(act.load_factor or 0.0) * 100.0,
            "record_time": act.record_time.strftime("%d/%m/%Y %H:%M") if act.record_time else "",
            "total_co": act.total_co2e,
        })

    monthly_values = []
    for m in range(1, 13):
        month_rows = scope1_services.ActivityDataService.get_by_record_time(db, y, [m])
        monthly_values.append(sum(float(act.total_co2e or 0.0) for act in month_rows))

    return {
        "categories": device_rows,
        "activities": activity_rows,
        "device_types": [item.value for item in DeviceTypeEnum],
        "fuel_types": [item.value for item in FuelTypeEnum],
        "total_scope1_co2": sum(float(act.total_co2e or 0.0) for act in activities),
        "trend_data": {"labels": [f"T{i}" for i in range(1, 13)], "values": monthly_values},
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

    # Mix in Tier 1 Equipments
    s1_summary = equipment_service.summary_by_scope(db, 1, year=y, month=month, quarter=quarter)
    t1_total = float(s1_summary["total_co2e"] or 0.0)
    t1_trend = [float(v) for v in s1_summary["monthly_totals"]]

    dashboard["kpis"]["total_co2e"] += t1_total
    
    # Update line chart
    if dashboard["line_chart"]["values"] and len(dashboard["line_chart"]["values"]) == 12:
        dashboard["line_chart"]["values"] = [a + b for a, b in zip(dashboard["line_chart"]["values"], t1_trend)]
    return templates.TemplateResponse("scope/scope_01.html", {
        "request": request,
        "user": _user_from_request(request),
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
    context = _scope1_emission_source_context(db, y, month, quarter, months)

    return templates.TemplateResponse("scope/scope_01_emission_source.html", {
        "request": request,
        "user": _user_from_request(request),
        "current_year": y,
        "current_month": month if month is not None else min(months),
        "period_ctx": _scope1_period_ctx(y, month, quarter, months),
        **context,
    })


@router.get("/scope1/tier1", response_class=HTMLResponse)
async def scope1_tier1_page(
    request: Request,
    year: int = Query(None),
    month: int = Query(None),
    quarter: int = Query(None),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    y = year or now.year
    months = _resolve_scope1_months(month, quarter)
    current_month = month if month is not None else min(months)

    equipment_service.ensure_default_scope1_categories(db)
    summary = equipment_service.summary_by_scope(db, 1, year=y, month=month, quarter=quarter)
    categories = equipment_service.list_categories(db, 1)
    equipments = equipment_service.list_equipments(db, 1)
    records = equipment_service.list_records(db, 1, year=y, month=month, quarter=quarter)

    categories_for_ui = []
    for category in categories:
        categories_for_ui.append({
            "id": category.id,
            "scope": category.scope,
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "sort_order": category.sort_order,
            "is_active": bool(category.is_active),
        })

    equipments_for_ui = []
    for equipment in equipments:
        category = next((c for c in categories if c.id == equipment.category_id), None)
        equipments_for_ui.append({
            "id": equipment.id,
            "category_id": equipment.category_id,
            "code": equipment.code,
            "name": equipment.name,
            "quantity": equipment.quantity,
            "unit": equipment.unit,
            "calculation_method": equipment.calculation_method.value if equipment.calculation_method else None,
            "category_code": category.code if category else "",
            "category_name": category.name if category else "",
            "total_co2e": next((item["total_co2e"] for item in summary["equipment_totals"] if item["id"] == equipment.id), 0.0),
        })

    records_for_ui = summary["records"]

    period_ctx = _scope1_period_ctx(y, month, quarter, months)

    return templates.TemplateResponse("scope/scope_01_tier1.html", {
        "request": request,
        "user": _user_from_request(request),
        "categories_json": categories_for_ui,
        "equipments_json": equipments_for_ui,
        "records_json": records_for_ui,
        "summary_json": summary,
        "calculation_methods": [m.value for m in CalculationMethodEnum],
        "current_year": y,
        "current_month": current_month,
        "period_ctx": period_ctx,
        "total_scope1_co2": summary.get("total_co2e", 0.0),
        "trend_data": {"labels": [f"T{i}" for i in range(1, 13)], "values": summary.get("monthly_totals", [0.0] * 12)},
    })

@router.get("/api/scope1/tier1/categories")
async def list_tier1_categories(db: Session = Depends(get_db)):
    categories = equipment_service.list_categories(db, 1)
    return {
        "items": [
            {
                "id": category.id,
                "scope": category.scope,
                "code": category.code,
                "name": category.name,
                "description": category.description,
                "sort_order": category.sort_order,
                "is_active": bool(category.is_active),
            }
            for category in categories
        ]
    }


@router.post("/api/scope1/tier1/categories")
async def create_tier1_category(payload: ScopeCategoryCreate, db: Session = Depends(get_db)):
    if int(payload.scope) != 1:
        raise HTTPException(status_code=400, detail="Scope 1 chỉ nhận phạm vi scope = 1")
    category = equipment_service.create_category(db, payload)
    return {
        "id": category.id,
        "scope": category.scope,
        "code": category.code,
        "name": category.name,
        "description": category.description,
        "sort_order": category.sort_order,
        "is_active": bool(category.is_active),
    }


@router.put("/api/scope1/tier1/categories/{category_id}")
async def update_tier1_category(category_id: int, payload: ScopeCategoryUpdate, db: Session = Depends(get_db)):
    category = equipment_service.update_category(db, category_id, payload)
    return {
        "id": category.id,
        "scope": category.scope,
        "code": category.code,
        "name": category.name,
        "description": category.description,
        "sort_order": category.sort_order,
        "is_active": bool(category.is_active),
    }


@router.delete("/api/scope1/tier1/categories/{category_id}")
async def delete_tier1_category(category_id: int, db: Session = Depends(get_db)):
    return equipment_service.delete_category(db, category_id)


@router.get("/api/scope1/tier1/equipments")
async def list_tier1_equipments(db: Session = Depends(get_db)):
    equipments = equipment_service.list_equipments(db, 1)
    categories = {category.id: category for category in equipment_service.list_categories(db, 1)}
    summary = equipment_service.summary_by_scope(db, 1)
    return {
        "items": [
            {
                "id": equipment.id,
                "category_id": equipment.category_id,
                "code": equipment.code,
                "name": equipment.name,
                "quantity": equipment.quantity,
                "unit": equipment.unit,
                "calculation_method": equipment.calculation_method.value if equipment.calculation_method else None,
                "emission_factor_json": equipment.emission_factor_json,
                "description": equipment.description,
                "category_code": categories.get(equipment.category_id).code if categories.get(equipment.category_id) else "",
                "category_name": categories.get(equipment.category_id).name if categories.get(equipment.category_id) else "",
                "total_co2e": next((item["total_co2e"] for item in summary["equipment_totals"] if item["id"] == equipment.id), 0.0),
            }
            for equipment in equipments
        ]
    }


@router.post("/api/scope1/tier1/equipments")
async def create_tier1_equipment(payload: EquipmentCreate, db: Session = Depends(get_db)):
    equipment = equipment_service.create_equipment(db, 1, payload)
    return {
        "id": equipment.id,
        "category_id": equipment.category_id,
        "code": equipment.code,
        "name": equipment.name,
        "quantity": equipment.quantity,
        "unit": equipment.unit,
        "calculation_method": equipment.calculation_method.value if equipment.calculation_method else None,
        "emission_factor_json": equipment.emission_factor_json,
        "description": equipment.description,
    }


@router.get("/api/scope1/tier1/equipments/{equipment_id}")
async def get_tier1_equipment(equipment_id: int, db: Session = Depends(get_db)):
    payload = equipment_service.get_equipment_detail(db, 1, equipment_id)
    total_co2e = sum(float(record.co2e or 0.0) for record in payload["records"])
    return {
        "equipment": {
            "id": payload["equipment"].id,
            "category_id": payload["equipment"].category_id,
            "code": payload["equipment"].code,
            "name": payload["equipment"].name,
            "quantity": payload["equipment"].quantity,
            "unit": payload["equipment"].unit,
            "calculation_method": payload["equipment"].calculation_method.value if payload["equipment"].calculation_method else None,
            "emission_factor_json": payload["equipment"].emission_factor_json,
            "description": payload["equipment"].description,
        },
        "category": {
            "id": payload["category"].id,
            "scope": payload["category"].scope,
            "code": payload["category"].code,
            "name": payload["category"].name,
        } if payload["category"] else None,
        "records": [
            {
                "id": record.id,
                "record_time": record.record_time.strftime("%d/%m/%Y %H:%M") if record.record_time else "",
                "co2e": record.co2e,
                "input_json": record.input_json,
            }
            for record in payload["records"]
        ],
        "total_co2e": total_co2e,
    }


@router.put("/api/scope1/tier1/equipments/{equipment_id}")
async def update_tier1_equipment(equipment_id: int, payload: EquipmentUpdate, db: Session = Depends(get_db)):
    equipment = equipment_service.update_equipment(db, 1, equipment_id, payload)
    return {
        "id": equipment.id,
        "category_id": equipment.category_id,
        "code": equipment.code,
        "name": equipment.name,
        "quantity": equipment.quantity,
        "unit": equipment.unit,
        "calculation_method": equipment.calculation_method.value if equipment.calculation_method else None,
        "emission_factor_json": equipment.emission_factor_json,
        "description": equipment.description,
    }


@router.delete("/api/scope1/tier1/equipments/{equipment_id}")
async def delete_tier1_equipment(equipment_id: int, db: Session = Depends(get_db)):
    return equipment_service.delete_equipment(db, 1, equipment_id)


@router.get("/api/scope1/tier1/records")
async def list_tier1_records(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    records = equipment_service.list_records(db, 1, year=year, month=month, quarter=quarter)
    equipments = {equipment.id: equipment for equipment in equipment_service.list_equipments(db, 1)}
    return {
        "items": [
            {
                "id": record.id,
                "equipment_id": record.equipment_id,
                "equipment_code": equipments.get(record.equipment_id).code if equipments.get(record.equipment_id) else "",
                "equipment_name": equipments.get(record.equipment_id).name if equipments.get(record.equipment_id) else "",
                "record_time": record.record_time.strftime("%d/%m/%Y %H:%M") if record.record_time else "",
                "co2e": record.co2e,
                "input_json": record.input_json,
            }
            for record in records
        ]
    }


@router.post("/api/scope1/tier1/records")
async def create_tier1_record(payload: EquipmentRecordCreate, db: Session = Depends(get_db)):
    record = equipment_service.create_record(db, 1, payload)
    return {
        "id": record.id,
        "equipment_id": record.equipment_id,
        "record_time": record.record_time.strftime("%d/%m/%Y %H:%M") if record.record_time else "",
        "input_json": record.input_json,
        "co2e": record.co2e,
    }

@router.delete("/api/scope1/tier1/records/{record_id}")
async def delete_tier1_record(record_id: int, db: Session = Depends(get_db)):
    return equipment_service.delete_record(db, 1, record_id)

# --- API ENDPOINTS ---
@router.post("/scope1/categories")
async def create_category(payload: DeviceCreate, db: Session = Depends(get_db)):
    return scope1_services.DeviceService.create(db, payload)

@router.put("/scope1/categories/{category_id}")
async def update_category(category_id: str, payload: DeviceUpdate, db: Session = Depends(get_db)):
    return scope1_services.DeviceService.update(db, category_id, payload)

@router.delete("/scope1/categories/{category_id}")
async def delete_category(category_id: str, db: Session = Depends(get_db)):
    return scope1_services.DeviceService.delete(db, category_id)


@router.post("/scope1/activities")
async def create_activity(payload: ActivityDataCreate, db: Session = Depends(get_db)):
    return scope1_services.ActivityDataService.create(db, payload)

@router.put("/scope1/activities/{activity_id}")
async def update_activity(activity_id: int, payload: ActivityDataUpdate, db: Session = Depends(get_db)):
    return scope1_services.ActivityDataService.update(db, activity_id, payload)

@router.delete("/scope1/activities/{activity_id}")
async def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    return scope1_services.ActivityDataService.delete(db, activity_id)

@router.delete("/api/scope1/activities/bulk")
async def delete_activities_bulk(payload: BulkDeleteRequest, request: Request, db: Session = Depends(get_db)):
    for act_id in payload.ids:
        try:
            scope1_services.ActivityDataService.delete(db, act_id)
        except Exception:
            pass
    return {"message": f"Đã xóa {len(payload.ids)} bản ghi thành công", "status": "success"}

@router.post("/scope1/activities/import")
async def import_activities(file: UploadFile = File(...), period_year: int = Query(...), period_month: int = Query(...), db: Session = Depends(get_db)):
    return await scope1_services.ActivityDataService.import_from_excel(db, file, period_year, period_month)

@router.get("/api/scope1/activities/import-template")
async def download_import_template(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db)
):
    payload = scope1_services.ActivityDataService.generate_excel_template(db, year, month)
    return StreamingResponse(
        iter([payload.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=VPEI_Scope1_Template_{year}.xlsx"}
    )

@router.post("/scope1/activities/update-period-status")
async def update_period_status(year: int = Query(...), month: int = Query(...), status: str = Query(...), db: Session = Depends(get_db)):
    return {"updated": 0, "new_status": status, "message": "Tính năng khóa sổ đã được vô hiệu hóa."}

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
