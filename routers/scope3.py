import io
import random
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse

from core.database import get_db
from core.security import decode_token, get_token_payload

# Container Services & Schemas
from services import container_service, container_activity_service
from services import equipment_service
from services.scope3_period_service import compute_scope3_period, build_scope3_comparison_payload
from schemas.container import ContainerCreate, ContainerUpdate
from schemas.emission_source import EquipmentCreate, EquipmentUpdate, EquipmentRecordCreate, ScopeCategoryCreate, ScopeCategoryUpdate
from models.emission_source import CalculationMethodEnum

# Ship Services & Schemas
from services import ship_service, ship_activity_service, ship_voyage_service
from schemas.ship import ShipCreate, ShipUpdate, ShipVoyageRequest
from models.audit_log import AuditLog

# Harbor Craft Services & Schemas (TÀU TRONG CẢNG)
from services import harbor_craft_service
from schemas.harbor_craft import HarborCraftCreate, HarborCraftUpdate
from models.harbor_craft import HarborCraftTypeEnum, EngineTypeEnum

# Other Vehicles (CAR/MOTORBIKE)
from services import other_vehicle_service
from schemas.other_vehicle import OtherVehicleCreate, OtherVehicleUpdate

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _actor_from_request(request: Request) -> str:
    payload = get_token_payload(request) or {}
    return payload.get("sub") or "system"


def _scope3_excel_column_names(df: pd.DataFrame) -> set[str]:
    return {str(c).strip() for c in df.columns}


SCOPE3_CONTAINER_IMPORT_COLUMNS = frozenset(
    {
        "Biển số xe",
        "Loại xe (Thường/Lạnh)",
        "Journey Type (both/import/export)",
        "Thời gian vào (YYYY-MM-DD HH:MM)",
        "Thời gian ra (YYYY-MM-DD HH:MM)",
        "Tải trọng tối đa (Tấn)",
        "Vận tốc C1 (km/h)",
        "Vận tốc C2 (km/h)",
        "Vận tốc C3 (km/h)",
        "Trọng lượng nhập (Tấn)",
        "Trọng lượng xuất (Tấn)",
        "Quãng đường C1 (km)",
        "Quãng đường C2 (km)",
        "Quãng đường C3 (km)",
        "Ghi chú",
    }
)

SCOPE3_SHIP_IMPORT_COLUMNS = frozenset(
    {
        "Tên tàu",
        "Loại tàu (VD: container_ship)",
        "Năm đóng",
        "DWT (Tấn)",
        "Thời gian vào cảng (YYYY-MM-DD HH:MM)",
        "Thời gian rời cảng (YYYY-MM-DD HH:MM)",
        "V_trip (km/h)",
        "V_maneuver (km/h)",
        "V_max (km/h)",
        "P_main (kW)",
        "RPM",
        "Loại Van (C3/SV)",
        "Động cơ MAN (TRUE/FALSE)",
    }
)

SCOPE3_HARBOR_CRAFT_IMPORT_COLUMNS = frozenset(
    {
        "Tên thiết bị",
        "Loại tàu (atb, barge, tugboat...)",
        "Loại động cơ (main/aux)",
        "Năm đóng",
        "Power (kW)",
        "Giờ hoạt động",
        "Dùng RD99 (TRUE/FALSE)",
        "Engine Tier (0-3 hoặc 4)",
        "Thời gian (YYYY-MM-DD HH:MM)",
    }
)

SCOPE3_OTHER_VEHICLE_IMPORT_COLUMNS = frozenset(
    {
        "Loại xe (car/motorbike)",
        "Số lượng xe",
        "Thời gian (YYYY-MM-DD HH:MM)",
    }
)


def _validate_scope3_import_excel(df: pd.DataFrame, kind: str) -> None:
    """kind: container | ship | harbor_craft | other_vehicle — đúng mẫu cột + gợi ý khi nhầm loại file."""
    if df is None or len(df) == 0:
        raise HTTPException(status_code=400, detail="File Excel không có dòng dữ liệu.")

    cols = _scope3_excel_column_names(df)

    if kind == "container":
        if SCOPE3_SHIP_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu tàu biển. Chọn loại Tàu biển khi import hoặc dùng mẫu Excel xe container.",
            )
        if SCOPE3_HARBOR_CRAFT_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu tàu trong cảng. Chọn đúng loại phương tiện hoặc dùng mẫu Excel xe container.",
            )
        missing = SCOPE3_CONTAINER_IMPORT_COLUMNS - cols
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"File không đúng mẫu xe container. Thiếu cột: {', '.join(sorted(missing))}.",
            )
    elif kind == "ship":
        if SCOPE3_CONTAINER_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu xe container. Chọn loại Xe container khi import hoặc dùng mẫu Excel tàu biển.",
            )
        if SCOPE3_HARBOR_CRAFT_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu tàu trong cảng. Chọn Tàu trong cảng hoặc dùng mẫu Excel tàu biển.",
            )
        missing = SCOPE3_SHIP_IMPORT_COLUMNS - cols
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"File không đúng mẫu tàu biển. Thiếu cột: {', '.join(sorted(missing))}.",
            )
    elif kind == "harbor_craft":
        if SCOPE3_CONTAINER_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu xe container. Chọn Xe container hoặc dùng mẫu Excel tàu trong cảng.",
            )
        if SCOPE3_SHIP_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu tàu biển. Chọn Tàu biển hoặc dùng mẫu Excel tàu trong cảng.",
            )
        missing = SCOPE3_HARBOR_CRAFT_IMPORT_COLUMNS - cols
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"File không đúng mẫu tàu trong cảng. Thiếu cột: {', '.join(sorted(missing))}.",
            )
    elif kind == "other_vehicle":
        if SCOPE3_CONTAINER_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu xe container. Chọn đúng loại Xe thường hoặc dùng mẫu Excel xe thường.",
            )
        if SCOPE3_SHIP_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu tàu biển. Chọn đúng loại Xe thường hoặc dùng mẫu Excel xe thường.",
            )
        if SCOPE3_HARBOR_CRAFT_IMPORT_COLUMNS <= cols:
            raise HTTPException(
                status_code=400,
                detail="File là mẫu tàu trong cảng. Chọn đúng loại Xe thường hoặc dùng mẫu Excel xe thường.",
            )
        missing = SCOPE3_OTHER_VEHICLE_IMPORT_COLUMNS - cols
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"File không đúng mẫu xe thường. Thiếu cột: {', '.join(sorted(missing))}.",
            )
    else:
        raise HTTPException(status_code=500, detail="Cấu hình import không hợp lệ.")


def _scope3_import_result(imported_count: int, total_rows: int) -> dict:
    return {
        "message": "Import success",
        "imported": imported_count,
        "total_rows": total_rows,
        "failed_rows": total_rows - imported_count,
    }


# =====================================================================
# ─── UI PAGES (HTML) ───────────────────────────────────────
# =====================================================================

@router.get("/scope3", response_class=HTMLResponse)
async def scope3_page(
    request: Request,
    db: Session = Depends(get_db),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
):
    """Render Scope 3 main page (Combined Summary)"""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    # 1. Lấy summary của Container
    container_summary = container_service.get_scope3_summary(db)
    
    # Query database for totals to avoid loading all rows
    from sqlalchemy import func
    from models.ship import Ship
    from models.harbor_craft import HarborCraft
    from models.other_vehicle import OtherVehicle
    
    # 2. Lấy summary của Ship
    ship_total_co2 = db.query(func.sum(Ship.total_co2)).scalar() or 0.0
    ship_count = db.query(func.count(Ship.id)).scalar() or 0
    
    # 3. Lấy summary của Tàu cảng (Harbor Craft)
    harbor_total_co2 = db.query(func.sum(HarborCraft.e_total)).scalar() or 0.0
    harbor_count = db.query(func.count(HarborCraft.id)).scalar() or 0

    other_total_co2 = db.query(func.sum(OtherVehicle.e_total)).scalar() or 0.0
    other_count = db.query(func.count(OtherVehicle.id)).scalar() or 0
    
    # 4. Gộp dữ liệu Summary
    total_co2e = container_summary.get("total_co2", 0.0) + ship_total_co2 + harbor_total_co2 + other_total_co2
    total_trips = container_summary.get("total_trips", 0) + ship_count + harbor_count + other_count
    
    summary = {
        **container_summary,
        "container_co2e": container_summary.get("total_co2", 0.0),
        "ship_co2e": ship_total_co2,
        "harbor_co2e": harbor_total_co2,
        "other_vehicle_co2e": other_total_co2,
        "total_co2e": total_co2e,
        "total_trips": total_trips
    }
    
    y = year or datetime.now().year
    s3 = compute_scope3_period(db, y, month, quarter)
    equipment_summary = equipment_service.summary_by_scope(db, 3, year=y, month=month, quarter=quarter)
    summary = {
        "total_co2": round(s3["total_co2e"], 2),
        "total_co2e": round(s3["total_co2e"], 2),
        "container_co2e": round(s3["container_co2e"], 2),
        "ship_co2e": round(s3["ship_co2e"], 2),
        "voyage_co2e": round(s3.get("voyage_co2e", 0.0), 2),
        "harbor_co2e": round(s3["harbor_co2e"], 2),
        "other_vehicle_co2e": round(s3["other_vehicle_co2e"], 2),
        "equipment_co2e": round(equipment_summary["total_co2e"], 2),
        "total_trips": s3["record_count"],
        "total_ships": s3["n_ships"],
        "n_other_vehicles": s3["n_other_vehicles"],
    }

    equipment_service.ensure_default_scope3_categories(db)
    categories = equipment_service.list_categories(db, 3)
    equipments = equipment_service.list_equipments(db, 3)
    records = equipment_service.list_records(db, 3, year=y, month=month, quarter=quarter)

    return templates.TemplateResponse(
        "scope/scope3.html",
        {
            "request": request,
            "user": current_user,
            "summary": summary,
            "scope3_categories_json": [
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
            ],
            "scope3_equipments_json": [
                {
                    "id": equipment.id,
                    "category_id": equipment.category_id,
                    "code": equipment.code,
                    "name": equipment.name,
                    "quantity": equipment.quantity,
                    "unit": equipment.unit,
                    "calculation_method": equipment.calculation_method.value if equipment.calculation_method else None,
                    "category_code": next((category.code for category in categories if category.id == equipment.category_id), ""),
                    "category_name": next((category.name for category in categories if category.id == equipment.category_id), ""),
                    "total_co2e": next((item["total_co2e"] for item in equipment_summary["equipment_totals"] if item["id"] == equipment.id), 0.0),
                }
                for equipment in equipments
            ],
            "scope3_records_json": equipment_summary["records"],
            "scope3_calculation_methods": [m.value for m in CalculationMethodEnum],
        },
    )


@router.get("/scope3/manager", response_class=HTMLResponse)
async def scope3_manager_page(request: Request, db: Session = Depends(get_db)):
    """Render Scope 3 manager/history page (Combined Audit Logs)"""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    c_history = container_activity_service.get_scope3_activity_history(db)
    s_history = ship_activity_service.get_ship_activity_history(db)

    combined_logs = c_history["logs"] + s_history["logs"]
    combined_logs.sort(
        key=lambda x: datetime.strptime(x["time"], "%d/%m/%Y %H:%M:%S"), 
        reverse=True
    )

    combined_years = sorted(
        list(set(c_history["available_years"] + s_history["available_years"])), 
        reverse=True
    )

    return templates.TemplateResponse(
        "scope/scope3_manager.html",
        {
            "request": request,
            "user": current_user,
            "audit_json": combined_logs,
            "available_years_json": combined_years,
            "can_delete": bool(current_user.get("is_admin")),
        },
    )


@router.get("/scope3/ndv", response_class=HTMLResponse)
async def scope3_ndv_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    return templates.TemplateResponse(
        "scope/NDV.html",
        {
            "request": request,
        },
    )


@router.get("/scope3/ndv/map_data")
async def scope3_ndv_data():
    file_path = Path(__file__).resolve().parent.parent / "templates" / "data" / "ndv_map_data.js"
    return FileResponse(str(file_path), media_type="application/javascript")

@router.get("/scope3/ndv/zone_data")
async def scope3_ndv_zone_data():
    file_path = Path(__file__).resolve().parent.parent / "templates" / "data" / "ndv_zone_data.js"
    return FileResponse(str(file_path), media_type="application/javascript")

@router.get("/scope3/ship_voyage_map", response_class=HTMLResponse)
async def scope3_ship_voyage_map_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    return templates.TemplateResponse(
        "scope/voyage_map.html",
        {
            "request": request,
        },
    )

@router.get("/scope3/voyage_route_data")    
async def scope3_voyage_route_data():
    file_path = Path(__file__).resolve().parent.parent / "templates" / "data" / "voyage_route_data.js"
    return FileResponse(str(file_path), media_type="application/javascript")

@router.get("/api/scope3/equipment/categories")
async def list_scope3_equipment_categories(db: Session = Depends(get_db)):
    equipment_service.ensure_default_scope3_categories(db)
    categories = equipment_service.list_categories(db, 3)
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


@router.post("/api/scope3/equipment/categories")
async def create_scope3_equipment_category(payload: ScopeCategoryCreate, db: Session = Depends(get_db)):
    if int(payload.scope) != 3:
        raise HTTPException(status_code=400, detail="Scope 3 chỉ nhận phạm vi scope = 3")
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


@router.get("/api/scope3/equipment/items")
async def list_scope3_equipment_items(db: Session = Depends(get_db)):
    equipment_service.ensure_default_scope3_categories(db)
    equipments = equipment_service.list_equipments(db, 3)
    categories = {category.id: category for category in equipment_service.list_categories(db, 3)}
    summary = equipment_service.summary_by_scope(db, 3)
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


@router.post("/api/scope3/equipment/items")
async def create_scope3_equipment_item(payload: EquipmentCreate, db: Session = Depends(get_db)):
    equipment = equipment_service.create_equipment(db, 3, payload)
    category = equipment_service.get_equipment_detail(db, 3, equipment.id)["category"]
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
        "category_code": category.code if category else "",
        "category_name": category.name if category else "",
        "was_quantity_incremented": bool(getattr(equipment, "_was_quantity_incremented", False)),
    }


@router.get("/api/scope3/equipment/items/{equipment_id}")
async def get_scope3_equipment_item(equipment_id: int, db: Session = Depends(get_db)):
    payload = equipment_service.get_equipment_detail(db, 3, equipment_id)
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


@router.put("/api/scope3/equipment/items/{equipment_id}")
async def update_scope3_equipment_item(equipment_id: int, payload: EquipmentUpdate, db: Session = Depends(get_db)):
    equipment = equipment_service.update_equipment(db, 3, equipment_id, payload)
    detail = equipment_service.get_equipment_detail(db, 3, equipment.id)
    category = detail["category"]
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
        "category_code": category.code if category else "",
        "category_name": category.name if category else "",
        "total_co2e": sum(float(record.co2e or 0.0) for record in detail["records"]),
    }


@router.delete("/api/scope3/equipment/items/{equipment_id}")
async def delete_scope3_equipment_item(equipment_id: int, db: Session = Depends(get_db)):
    return equipment_service.delete_equipment(db, 3, equipment_id)


@router.post("/api/scope3/equipment/records")
async def create_scope3_equipment_record(payload: EquipmentRecordCreate, db: Session = Depends(get_db)):
    record = equipment_service.create_record(db, 3, payload)
    return {
        "id": record.id,
        "equipment_id": record.equipment_id,
        "record_time": record.record_time.strftime("%d/%m/%Y %H:%M") if record.record_time else "",
        "input_json": record.input_json,
        "co2e": record.co2e,
    }


@router.get("/api/scope3/equipment/records")
async def list_scope3_equipment_records(db: Session = Depends(get_db)):
    summary = equipment_service.summary_by_scope(db, 3)
    return {"items": summary["records"], "count": len(summary["records"])}


@router.delete("/api/scope3/equipment/records/{record_id}")
async def delete_scope3_equipment_record(record_id: int, db: Session = Depends(get_db)):
    return equipment_service.delete_record(db, 3, record_id)


# =====================================================================
# ─── EXCEL IMPORT & TEMPLATE ENDPOINTS ───────────────────────────────
# =====================================================================

@router.get("/api/scope3/containers/template")
async def download_container_template():
    now = datetime.now()
    dummy_data = []
    journey_types = ["both", "import", "export"]
    plates = ["51C", "51H", "29H", "15C", "43C", "61C", "60C"]
    
    for i in range(1, 11):
        j_type = random.choice(journey_types)
        max_w = random.choice([20.0, 30.0, 40.0])
        in_w = round(random.uniform(5.0, max_w), 1) if j_type in ["both", "import"] else 0.0
        out_w = round(random.uniform(5.0, max_w), 1) if j_type in ["both", "export"] else 0.0
        hours_in = random.randint(12, 72)
        hours_out = random.randint(1, hours_in - 2)
        
        dummy_data.append({
            "Biển số xe": f"{random.choice(plates)}-{random.randint(10000, 99999)}",
            "Loại xe (Thường/Lạnh)": random.choice(["Thường", "Lạnh"]),
            "Journey Type (both/import/export)": j_type,
            "Thời gian vào (YYYY-MM-DD HH:MM)": (now - timedelta(hours=hours_in, minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M"),
            "Thời gian ra (YYYY-MM-DD HH:MM)": (now - timedelta(hours=hours_out, minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M"),
            "Tải trọng tối đa (Tấn)": max_w,
            "Vận tốc C1 (km/h)": round(random.uniform(10.0, 20.0), 1),
            "Vận tốc C2 (km/h)": round(random.uniform(30.0, 60.0), 1),
            "Vận tốc C3 (km/h)": round(random.uniform(10.0, 20.0), 1),
            "Trọng lượng nhập (Tấn)": in_w,
            "Trọng lượng xuất (Tấn)": out_w,
            "Quãng đường C1 (km)": round(random.uniform(1.0, 5.0), 1),
            "Quãng đường C2 (km)": round(random.uniform(10.0, 50.0), 1),
            "Quãng đường C3 (km)": round(random.uniform(1.0, 5.0), 1),
            "Ghi chú": f"Chuyến hàng mẫu {i}"
        })
        
    df = pd.DataFrame(dummy_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data_Xe_Container', index=False)
        for column in df:
            column_length = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Data_Xe_Container'].set_column(col_idx, col_idx, column_length + 2)
            
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": "attachment; filename=Template_Import_Xe_Container.xlsx"}
    )


@router.get("/api/scope3/ships/template")
async def download_ship_template():
    now = datetime.now()
    dummy_data = []
    ship_types = ["container_ship", "bulk_carrier", "general_cargo_ship", "oil_tanker", "roro_ship"]
    ship_prefixes = ["Ocean", "Star", "Express", "Pioneer", "Voyager", "Marine", "Glory"]
    
    for i in range(1, 11):
        v_max = round(random.uniform(20.0, 26.0), 1)
        hours_in = random.randint(48, 240)
        hours_out = random.randint(1, 24)
        
        dummy_data.append({
            "Tên tàu": f"VPEI {random.choice(ship_prefixes)} {random.randint(10, 99)}",
            "Loại tàu (VD: container_ship)": random.choice(ship_types),
            "Năm đóng": random.randint(2005, 2023),
            "DWT (Tấn)": round(random.uniform(20000.0, 150000.0), 0),
            "Thời gian vào cảng (YYYY-MM-DD HH:MM)": (now - timedelta(hours=hours_in, minutes=random.randint(0,59))).strftime("%Y-%m-%d %H:%M"),
            "Thời gian rời cảng (YYYY-MM-DD HH:MM)": (now - timedelta(hours=hours_out, minutes=random.randint(0,59))).strftime("%Y-%m-%d %H:%M"),
            "V_trip (km/h)": round(random.uniform(12.0, v_max - 2), 1),
            "V_maneuver (km/h)": round(random.uniform(4.0, 8.0), 1),
            "V_max (km/h)": v_max,
            "P_main (kW)": round(random.uniform(10000.0, 50000.0), 0),
            "RPM": random.choice([100.0, 120.0, 150.0, 180.0]),
            "Loại Van (C3/SV)": random.choice(["C3", "SV"]),
            "Động cơ MAN (TRUE/FALSE)": random.choice([True, False])
        })
        
    df = pd.DataFrame(dummy_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data_Tau_Bien', index=False)
        for column in df:
            column_length = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Data_Tau_Bien'].set_column(col_idx, col_idx, column_length + 2)
            
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": "attachment; filename=Template_Import_Tau_Bien.xlsx"}
    )


@router.get("/api/scope3/harbor_crafts/template")
async def download_harbor_craft_template():
    now = datetime.now()
    dummy_data = []
    device_names = ["Tàu lai dắt 01", "Tàu lai dắt 02", "Tàu hoa tiêu 01", "Tàu kéo 01"]
    craft_types = [e.value for e in HarborCraftTypeEnum]
    
    for i in range(1, 11):
        dummy_data.append({
            "Tên thiết bị": random.choice(device_names),
            "Loại tàu (atb, barge, tugboat...)": random.choice(craft_types),
            "Loại động cơ (main/aux)": random.choice(["main", "aux"]),
            "Năm đóng": random.randint(2005, 2023),
            "Power (kW)": round(random.uniform(100.0, 1500.0), 1),
            "Giờ hoạt động": round(random.uniform(5.0, 24.0), 1),
            "Dùng RD99 (TRUE/FALSE)": False,
            "Engine Tier (0-3 hoặc 4)": "0-3",
            "Thời gian (YYYY-MM-DD HH:MM)": (now - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d %H:%M")
        })
        
    df = pd.DataFrame(dummy_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data_Tau_Cang', index=False)
        for column in df:
            column_length = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Data_Tau_Cang'].set_column(col_idx, col_idx, column_length + 2)
            
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": "attachment; filename=Template_Import_Tau_Cang.xlsx"}
    )


@router.get("/api/scope3/other_vehicles/template")
async def download_other_vehicle_template():
    now = datetime.now()
    dummy_data = []
    types = ["car", "motorbike"]

    for i in range(1, 11):
        dummy_data.append({
            "Loại xe (car/motorbike)": random.choice(types),
            "Số lượng xe": random.randint(1, 50),
            "Thời gian (YYYY-MM-DD HH:MM)": (now - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d %H:%M"),
        })

    df = pd.DataFrame(dummy_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data_Xe_Thuong', index=False)
        for column in df:
            column_length = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Data_Xe_Thuong'].set_column(col_idx, col_idx, column_length + 2)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Template_Import_Xe_Thuong.xlsx"},
    )


# --- IMPORTS EXCEL POST ENDPOINTS ---
@router.post("/api/scope3/containers/import")
async def import_containers(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không đọc được file Excel: {str(e)}") from e

    df = df.fillna(0)
    _validate_scope3_import_excel(df, "container")

    imported_count = 0
    actor = _actor_from_request(request)

    for _, row in df.iterrows():
        try:
            start_t = pd.to_datetime(row["Thời gian vào (YYYY-MM-DD HH:MM)"])
            end_t = pd.to_datetime(row["Thời gian ra (YYYY-MM-DD HH:MM)"])
            
            is_refri = False
            if "Loại xe (Thường/Lạnh)" in row:
                val = str(row["Loại xe (Thường/Lạnh)"]).strip().lower()
                if val == "lạnh":
                    is_refri = True

            payload = ContainerCreate(
                license_plate=str(row["Biển số xe"]),
                is_refrigerated=is_refri,
                journey_type=str(row["Journey Type (both/import/export)"]) if row["Journey Type (both/import/export)"] else "both",
                start_time=start_t,
                end_time=end_t,
                max_weight=float(row["Tải trọng tối đa (Tấn)"]),
                velocity_1=float(row["Vận tốc C1 (km/h)"]),
                velocity_2=float(row["Vận tốc C2 (km/h)"]),
                velocity_3=float(row["Vận tốc C3 (km/h)"]),
                input_weight=float(row["Trọng lượng nhập (Tấn)"]),
                output_weight=float(row["Trọng lượng xuất (Tấn)"]),
                distance_1=float(row["Quãng đường C1 (km)"]),
                distance_2=float(row["Quãng đường C2 (km)"]),
                distance_3=float(row["Quãng đường C3 (km)"]),
                note=str(row["Ghi chú"]) if row["Ghi chú"] != 0 else "",
            )
            container_service.create_container(payload, db, actor=actor)
            imported_count += 1
        except Exception as e:
            print(f"Lỗi dòng xe container: {e}")
            continue

    total = len(df)
    if total > 0 and imported_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Không import được dòng nào. Kiểm tra định dạng thời gian và giá trị số trên từng dòng.",
        )

    return _scope3_import_result(imported_count, total)


@router.post("/api/scope3/ships/import")
async def import_ships(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không đọc được file Excel: {str(e)}") from e

    df = df.fillna(0)
    _validate_scope3_import_excel(df, "ship")

    imported_count = 0
    actor = _actor_from_request(request)

    for _, row in df.iterrows():
        try:
            start_t = pd.to_datetime(row["Thời gian vào cảng (YYYY-MM-DD HH:MM)"])
            end_t = pd.to_datetime(row["Thời gian rời cảng (YYYY-MM-DD HH:MM)"])

            p_main = float(row["P_main (kW)"])
            payload = ShipCreate(
                name=str(row["Tên tàu"]),
                ship_type=str(row["Loại tàu (VD: container_ship)"]),
                year_built=int(row["Năm đóng"]),
                buoy=0,
                deadweight_tonnage=float(row["DWT (Tấn)"]),
                start_time=start_t,
                end_time=end_t,
                v_trip=float(row["V_trip (km/h)"]),
                v_maneuver=float(row["V_maneuver (km/h)"]),
                v_max=float(row["V_max (km/h)"]),
                P_main=p_main,
                P_aux=1/5*p_main,
                rpm=float(row["RPM"]),
                valve_type=str(row["Loại Van (C3/SV)"]),
                is_man=bool(row["Động cơ MAN (TRUE/FALSE)"]),
            )
            ship_service.create_ship(payload, db, actor=actor)
            imported_count += 1
        except Exception as e:
            print(f"Lỗi dòng tàu biển: {e}")
            continue

    total = len(df)
    if total > 0 and imported_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Không import được dòng nào. Kiểm tra định dạng thời gian và giá trị số trên từng dòng.",
        )

    return _scope3_import_result(imported_count, total)


@router.post("/api/scope3/harbor_crafts/import")
async def import_harbor_crafts(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import dữ liệu Tàu Trong Cảng từ file Excel (Đã fix lỗi ENUM)"""
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không đọc được file Excel: {str(e)}") from e

    df = df.fillna(0)
    _validate_scope3_import_excel(df, "harbor_craft")

    imported_count = 0
    actor = _actor_from_request(request)

    for _, row in df.iterrows():
        try:
            record_time_raw = row.get("Thời gian (YYYY-MM-DD HH:MM)")
            if pd.isna(record_time_raw) or not record_time_raw:
                record_t = datetime.now()
            else:
                record_t = pd.to_datetime(record_time_raw)

            raw_craft = str(row.get("Loại tàu (atb, barge, tugboat...)", "other")).strip().lower()
            try:
                c_type = HarborCraftTypeEnum(raw_craft)
            except ValueError:
                c_type = HarborCraftTypeEnum.OTHER

            raw_engine = str(row.get("Loại động cơ (main/aux)", "main")).strip().lower()
            try:
                e_type = EngineTypeEnum(raw_engine)
            except ValueError:
                e_type = EngineTypeEnum.MAIN

            payload = HarborCraftCreate(
                device_name=str(row.get("Tên thiết bị", "Tàu Cảng")),
                craft_type=c_type,
                engine_type=e_type,
                year_built=int(row.get("Năm đóng", 2010)),
                power=float(row.get("Power (kW)", 0)),
                activity_hours=float(row.get("Giờ hoạt động", 0)),
                use_rd99=bool(row.get("Dùng RD99 (TRUE/FALSE)", False)),
                engine_tier=str(row.get("Engine Tier (0-3 hoặc 4)", "0-3")),
                record_time=record_t,
            )
            harbor_craft_service.create_harbor_craft(payload, db, actor=actor)
            imported_count += 1
        except Exception as e:
            print(f"Lỗi dòng tàu cảng: {e}")
            continue

    total = len(df)
    if total > 0 and imported_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Không import được dòng nào. Kiểm tra định dạng thời gian và giá trị số trên từng dòng.",
        )

    return _scope3_import_result(imported_count, total)


@router.post("/api/scope3/other_vehicles/import")
async def import_other_vehicles(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không đọc được file Excel: {str(e)}") from e

    df = df.fillna(0)
    _validate_scope3_import_excel(df, "other_vehicle")

    imported_count = 0
    actor = _actor_from_request(request)

    for _, row in df.iterrows():
        try:
            record_time_raw = row.get("Thời gian (YYYY-MM-DD HH:MM)")
            if pd.isna(record_time_raw) or not record_time_raw:
                record_t = datetime.now()
            else:
                record_t = pd.to_datetime(record_time_raw)

            raw_type = str(row.get("Loại xe (car/motorbike)", "car")).strip().lower()
            if raw_type not in ("car", "motorbike"):
                raw_type = "car"

            payload = OtherVehicleCreate(
                vehicle_type=raw_type,
                vehicle_count=int(row.get("Số lượng xe", 1) or 1),
                record_time=record_t,
            )
            other_vehicle_service.create_other_vehicle(payload, db, actor=actor)
            imported_count += 1
        except Exception as e:
            print(f"Lỗi dòng xe thường: {e}")
            continue

    total = len(df)
    if total > 0 and imported_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Không import được dòng nào. Kiểm tra định dạng thời gian và giá trị số trên từng dòng.",
        )

    return _scope3_import_result(imported_count, total)


# =====================================================================
# ─── API ENDPOINTS CHO CRUD DỮ LIỆU (JSON) ───────────────────────────
# =====================================================================

# ─── CONTAINER & OTHER VEHICLES API ───
@router.post("/api/scope3/containers")
async def create_container(container: ContainerCreate, request: Request, db: Session = Depends(get_db)):
    return container_service.create_container(container, db, actor=_actor_from_request(request))

@router.get("/api/scope3/containers")
async def list_containers(db: Session = Depends(get_db)):
    containers = container_service.get_all_containers(db)
    items = sorted(
        containers,
        key=lambda x: x.get("start_time") or x.get("created_at") or "",
        reverse=True,
    )
    return {"items": items, "count": len(items)}

@router.get("/api/scope3/containers/{container_id}")
async def get_container(container_id: int, db: Session = Depends(get_db)):
    return container_service.get_container_by_id(container_id, db)

@router.put("/api/scope3/containers/{container_id}")
async def update_container(container_id: int, container: ContainerUpdate, request: Request, db: Session = Depends(get_db)):
    return container_service.update_container(container_id, container, db, actor=_actor_from_request(request))

from pydantic import BaseModel
class BulkDeleteRequest(BaseModel):
    ids: list[int]

@router.delete("/api/scope3/containers/bulk")
async def delete_containers_bulk(payload: BulkDeleteRequest, request: Request, db: Session = Depends(get_db)):
    deleted_count = 0
    actor = _actor_from_request(request)
    for c_id in payload.ids:
        try:
            container_service.delete_container(c_id, db, actor)
            deleted_count += 1
        except Exception:
            pass
    return {"message": f"Deleted {deleted_count} containers"}

@router.delete("/api/scope3/containers/{container_id}")
async def delete_container(container_id: int, request: Request, db: Session = Depends(get_db)):
    return container_service.delete_container(container_id, db, actor=_actor_from_request(request))


# ─── SHIP API ───
@router.post("/api/scope3/ships")
async def create_ship_endpoint(ship: ShipCreate, request: Request, db: Session = Depends(get_db)):
    return ship_service.create_ship(ship, db, actor=_actor_from_request(request))

@router.get("/api/scope3/ships")
async def list_ships(db: Session = Depends(get_db)):
    ships = ship_service.get_all_ships(db)
    return {"items": ships, "count": len(ships)}

@router.get("/api/scope3/ships/{ship_id}")
async def get_ship_endpoint(ship_id: int, db: Session = Depends(get_db)):
    return ship_service.get_ship_by_id(ship_id, db)

@router.put("/api/scope3/ships/{ship_id}")
async def update_ship_endpoint(ship_id: int, ship: ShipUpdate, request: Request, db: Session = Depends(get_db)):
    return ship_service.update_ship(ship_id, ship, db, actor=_actor_from_request(request))

@router.delete("/api/scope3/ships/bulk")
async def delete_ships_bulk(payload: BulkDeleteRequest, request: Request, db: Session = Depends(get_db)):
    deleted_count = 0
    actor = _actor_from_request(request)
    for s_id in payload.ids:
        try:
            ship_service.delete_ship(s_id, db, actor)
            deleted_count += 1
        except Exception:
            pass
    return {"message": f"Deleted {deleted_count} ships"}

@router.delete("/api/scope3/ships/{ship_id}")
async def delete_ship_endpoint(ship_id: int, request: Request, db: Session = Depends(get_db)):
    return ship_service.delete_ship(ship_id, db, actor=_actor_from_request(request))


@router.post("/api/scope3/ships/voyage/calculate")
async def calculate_ship_voyage(payload: ShipVoyageRequest, request: Request, db: Session = Depends(get_db)):
    """Tính phát thải cho tuyến nhiều cảng (at sea + in port) và trả dữ liệu để vẽ map."""
    result = ship_voyage_service.calculate_ship_voyage_emissions(payload)
    saved = ship_voyage_service.save_ship_voyage_record(db, payload, result)
    result["record"] = saved
    return result


# ─── HARBOR CRAFT API (TÀU TRONG CẢNG) ───
@router.get("/api/scope3/harbor_crafts")
async def get_harbor_crafts(db: Session = Depends(get_db)):
    items = harbor_craft_service.get_all_harbor_crafts(db)
    return {"items": items, "count": len(items)}

@router.post("/api/scope3/harbor_crafts")
async def create_harbor_craft(payload: HarborCraftCreate, request: Request, db: Session = Depends(get_db)):
    try:
        return harbor_craft_service.create_harbor_craft(payload, db, actor=_actor_from_request(request))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/scope3/harbor_crafts/{record_id}")
async def update_harbor_craft(record_id: int, payload: HarborCraftUpdate, request: Request, db: Session = Depends(get_db)):
    try:
        return harbor_craft_service.update_harbor_craft(record_id, payload, db, actor=_actor_from_request(request))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/scope3/harbor_crafts/bulk")
async def delete_harbor_crafts_bulk(payload: BulkDeleteRequest, request: Request, db: Session = Depends(get_db)):
    deleted_count = 0
    actor = _actor_from_request(request)
    for h_id in payload.ids:
        try:
            harbor_craft_service.delete_harbor_craft(h_id, db, actor)
            deleted_count += 1
        except Exception:
            pass
    return {"message": f"Deleted {deleted_count} harbor crafts"}

@router.delete("/api/scope3/harbor_crafts/{record_id}")
async def delete_harbor_craft(record_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        return harbor_craft_service.delete_harbor_craft(record_id, db, actor=_actor_from_request(request))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── OTHER VEHICLE API (CAR/MOTORBIKE) ───
@router.get("/api/scope3/other_vehicles")
async def list_other_vehicles(db: Session = Depends(get_db)):
    items = other_vehicle_service.get_all_other_vehicles(db)
    return {"items": items, "count": len(items)}

@router.post("/api/scope3/other_vehicles")
async def create_other_vehicle(payload: OtherVehicleCreate, request: Request, db: Session = Depends(get_db)):
    return other_vehicle_service.create_other_vehicle(payload, db, actor=_actor_from_request(request))

@router.get("/api/scope3/other_vehicles/{record_id}")
async def get_other_vehicle(record_id: int, db: Session = Depends(get_db)):
    return other_vehicle_service.get_other_vehicle_by_id(record_id, db)

@router.put("/api/scope3/other_vehicles/{record_id}")
async def update_other_vehicle(record_id: int, payload: OtherVehicleUpdate, request: Request, db: Session = Depends(get_db)):
    return other_vehicle_service.update_other_vehicle(record_id, payload, db, actor=_actor_from_request(request))

@router.delete("/api/scope3/other_vehicles/{record_id}")
async def delete_other_vehicle(record_id: int, request: Request, db: Session = Depends(get_db)):
    return other_vehicle_service.delete_other_vehicle(record_id, db, actor=_actor_from_request(request))


@router.get("/api/scope3/ship_voyages")
async def list_ship_voyages(db: Session = Depends(get_db)):
    items = ship_voyage_service.get_all_ship_voyages(db)
    return {"items": items, "count": len(items)}


@router.delete("/api/scope3/ship_voyages/bulk")
async def delete_ship_voyages_bulk(payload: BulkDeleteRequest, request: Request, db: Session = Depends(get_db)):
    deleted_count = 0
    for record_id in payload.ids:
        try:
            ship_voyage_service.delete_ship_voyage(record_id, db)
            deleted_count += 1
        except Exception:
            pass
    return {"message": f"Đã xóa {deleted_count} bản ghi hải trình"}


@router.delete("/api/scope3/ship_voyages/{record_id}")
async def delete_ship_voyage(record_id: int, request: Request, db: Session = Depends(get_db)):
    ship_voyage_service.delete_ship_voyage(record_id, db)
    return {"message": "Đã xóa bản ghi hải trình"}


# ─── COMBINED SUMMARY & AUDIT API ENDPOINTS ──────────────────

@router.get("/api/scope3/summary")
async def get_scope3_summary(
    db: Session = Depends(get_db),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
):
    """Tổng hợp Scope 3 theo kỳ (năm/tháng/quý) — cùng logic trang /scope3 và dashboard."""
    y = year or datetime.now().year
    s3 = compute_scope3_period(db, y, month, quarter)
    return {
        "total_co2": round(s3["total_co2e"], 2),
        "total_co2e": round(s3["total_co2e"], 2),
        "container_co2e": round(s3["container_co2e"], 2),
        "ship_co2e": round(s3["ship_co2e"], 2),
        "voyage_co2e": round(s3.get("voyage_co2e", 0.0), 2),
        "harbor_co2e": round(s3["harbor_co2e"], 2),
        "truck_co2e": round(s3["truck_co2e"], 2),
        "other_vehicle_co2e": round(s3["other_vehicle_co2e"], 2),
        "equipment_co2e": round(s3.get("equipment_co2e", 0.0), 2),
        "record_count": s3["record_count"],
        "total_trips": s3["record_count"],
        "total_ships": s3["n_ships"],
        "n_containers": s3["n_containers"],
        "n_other_vehicles": s3["n_other_vehicles"],
        "n_harbor_crafts": s3["n_harbor_crafts"],
        "trend_container_monthly": s3["trend_container_monthly"],
        "trend_ship_monthly": s3["trend_ship_monthly"],
        "trend_voyage_monthly": s3.get("trend_voyage_monthly", [0.0] * 12),
        "trend_harbor_monthly": s3["trend_harbor_monthly"],
        "trend_other_vehicle_monthly": s3["trend_other_vehicle_monthly"],
        "trend_equipment_monthly": s3.get("trend_equipment_monthly", [0.0] * 12),
        "trend_monthly": s3["trend_monthly"],
    }


@router.get("/api/scope3/comparison-series")
async def scope3_comparison_series(
    db: Session = Depends(get_db),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
):
    """Chuỗi giá trị nhiều kỳ (năm/tháng/quý) để biểu đồ so sánh — cùng logic tổng hợp Scope 3."""
    y = year or datetime.now().year
    return build_scope3_comparison_payload(db, y, month, quarter)


@router.get("/api/scope3/manager/audit")
async def manager_audit_log(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get combined audit log for Scope 3 (Container + Ship)"""
    c_history = container_activity_service.get_scope3_activity_history(
        db, year=year, month=month, quarter=quarter
    )
    s_history = ship_activity_service.get_ship_activity_history(
        db, year=year, month=month, quarter=quarter
    )

    combined_logs = c_history["logs"] + s_history["logs"]
    combined_logs.sort(
        key=lambda x: datetime.strptime(x["time"], "%d/%m/%Y %H:%M:%S"), 
        reverse=True
    )

    combined_month_year = sorted(
        list(set(c_history["available_month_year"] + s_history["available_month_year"])),
        key=lambda v: (int(v.split("/")[1]), int(v.split("/")[0])), 
        reverse=True
    )
    
    combined_years = sorted(
        list(set(c_history["available_years"] + s_history["available_years"])), 
        reverse=True
    )

    return {
        "logs": combined_logs,
        "available_month_year": combined_month_year,
        "available_years": combined_years,
    }


@router.delete("/api/scope3/manager/audit/{activity_id}")
async def delete_audit_activity(
    activity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete audit activity (admin only) - Xử lý chung cho cả Container và Ship"""
    payload = get_token_payload(request) or {}
    if not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    
    # Lấy log ra để kiểm tra scope
    target = db.query(AuditLog).filter(AuditLog.id == activity_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
        
    # Gọi hàm xóa tương ứng
    if target.scope == "scope3_ship":
        return ship_activity_service.delete_ship_activity(db, activity_id)
    else:
        return container_activity_service.delete_scope3_activity(db, activity_id)
