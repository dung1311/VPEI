import io
import random
import pandas as pd
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse

from core.database import get_db
from core.security import decode_token, get_token_payload

# Container Services & Schemas
from services import container_service, container_activity_service, scope3_other_vehicle_service
from schemas.container import ContainerCreate, ContainerUpdate
from schemas.scope3_other_vehicle import Scope3OtherVehicleCreate

# Ship Services & Schemas
from services import ship_service, ship_activity_service
from schemas.ship import ShipCreate, ShipUpdate
from models.audit_log import AuditLog

# Harbor Craft Services & Schemas (TÀU TRONG CẢNG)
from services import harbor_craft_service
from schemas.harbor_craft import HarborCraftCreate, HarborCraftUpdate
from models.harbor_craft import HarborCraftTypeEnum, EngineTypeEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _actor_from_request(request: Request) -> str:
    payload = get_token_payload(request) or {}
    return payload.get("sub") or "system"


# =====================================================================
# ─── UI PAGES (HTML) ───────────────────────────────────────
# =====================================================================

@router.get("/scope3", response_class=HTMLResponse)
async def scope3_page(request: Request, db: Session = Depends(get_db)):
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
    
    # 2. Lấy summary của Ship
    ships = ship_service.get_all_ships(db)
    ship_total_co2 = sum(s.get("e_total", 0.0) if isinstance(s, dict) else getattr(s, "total_co2", getattr(s, "e_total", 0.0)) for s in ships)
    
    # 3. Lấy summary của Tàu cảng (Harbor Craft)
    harbors = harbor_craft_service.get_all_harbor_crafts(db)
    harbor_total_co2 = sum(h.get("e_total", 0.0) for h in harbors)
    
    # 4. Gộp dữ liệu Summary
    total_co2e = container_summary.get("total_co2", 0.0) + ship_total_co2 + harbor_total_co2
    total_trips = container_summary.get("total_trips", 0) + len(ships) + len(harbors)
    
    summary = {
        **container_summary,
        "container_co2e": container_summary.get("total_co2", 0.0),
        "ship_co2e": ship_total_co2,
        "harbor_co2e": harbor_total_co2,
        "total_co2e": total_co2e,
        "total_trips": total_trips
    }

    return templates.TemplateResponse(
        "scope/scope3.html",
        {
            "request": request,
            "user": current_user,
            "summary": summary,
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
            "Phao số (Buoy)": random.choice([0, 1, 2, 3]),
            "DWT (Tấn)": round(random.uniform(20000.0, 150000.0), 0),
            "Thời gian vào cảng (YYYY-MM-DD HH:MM)": (now - timedelta(hours=hours_in, minutes=random.randint(0,59))).strftime("%Y-%m-%d %H:%M"),
            "Thời gian rời cảng (YYYY-MM-DD HH:MM)": (now - timedelta(hours=hours_out, minutes=random.randint(0,59))).strftime("%Y-%m-%d %H:%M"),
            "V_trip (km/h)": round(random.uniform(12.0, v_max - 2), 1),
            "V_maneuver (km/h)": round(random.uniform(4.0, 8.0), 1),
            "V_max (km/h)": v_max,
            "P_main (kW)": round(random.uniform(10000.0, 50000.0), 0),
            "P_aux (kW)": round(random.uniform(1500.0, 5000.0), 0),
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
    device_names = ["Tàu lai dắt 01", "Tàu lai dắt 02", "Xà lan 01", "Tàu hoa tiêu 01", "Tàu kéo 01"]
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


# --- IMPORTS EXCEL POST ENDPOINTS ---
@router.post("/api/scope3/containers/import")
async def import_containers(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        df = df.fillna(0) 
        
        imported_count = 0
        actor = _actor_from_request(request)
        
        for _, row in df.iterrows():
            try:
                start_t = pd.to_datetime(row["Thời gian vào (YYYY-MM-DD HH:MM)"])
                end_t = pd.to_datetime(row["Thời gian ra (YYYY-MM-DD HH:MM)"])
                
                payload = ContainerCreate(
                    license_plate=str(row["Biển số xe"]),
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
                    note=str(row["Ghi chú"]) if row["Ghi chú"] != 0 else ""
                )
                container_service.create_container(payload, db, actor=actor)
                imported_count += 1
            except Exception as e:
                print(f"Lỗi dòng xe container: {e}")
                continue 
                
        return {"message": "Import success", "imported": imported_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đọc file Excel: {str(e)}")


@router.post("/api/scope3/ships/import")
async def import_ships(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        df = df.fillna(0)
        
        imported_count = 0
        actor = _actor_from_request(request)
        
        for _, row in df.iterrows():
            try:
                start_t = pd.to_datetime(row["Thời gian vào cảng (YYYY-MM-DD HH:MM)"])
                end_t = pd.to_datetime(row["Thời gian rời cảng (YYYY-MM-DD HH:MM)"])
                
                payload = ShipCreate(
                    name=str(row["Tên tàu"]),
                    ship_type=str(row["Loại tàu (VD: container_ship)"]),
                    year_built=int(row["Năm đóng"]),
                    buoy=int(row["Phao số (Buoy)"]),
                    deadweight_tonnage=float(row["DWT (Tấn)"]),
                    start_time=start_t,
                    end_time=end_t,
                    v_trip=float(row["V_trip (km/h)"]),
                    v_maneuver=float(row["V_maneuver (km/h)"]),
                    v_max=float(row["V_max (km/h)"]),
                    P_main=float(row["P_main (kW)"]),
                    P_aux=float(row["P_aux (kW)"]),
                    rpm=float(row["RPM"]),
                    valve_type=str(row["Loại Van (C3/SV)"]),
                    is_man=bool(row["Động cơ MAN (TRUE/FALSE)"])
                )
                ship_service.create_ship(payload, db, actor=actor)
                imported_count += 1
            except Exception as e:
                print(f"Lỗi dòng tàu biển: {e}")
                continue
                
        return {"message": "Import success", "imported": imported_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đọc file Excel: {str(e)}")


@router.post("/api/scope3/harbor_crafts/import")
async def import_harbor_crafts(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import dữ liệu Tàu Trong Cảng từ file Excel (Đã fix lỗi ENUM)"""
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        df = df.fillna(0)
        
        imported_count = 0
        actor = _actor_from_request(request)
        
        for _, row in df.iterrows():
            try:
                record_time_raw = row.get("Thời gian (YYYY-MM-DD HH:MM)")
                if pd.isna(record_time_raw) or not record_time_raw:
                    record_t = datetime.now()
                else:
                    record_t = pd.to_datetime(record_time_raw)
                
                # Ép kiểu an toàn sang Enum
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
                    record_time=record_t
                )
                harbor_craft_service.create_harbor_craft(payload, db, actor=actor)
                imported_count += 1
            except Exception as e:
                print(f"Lỗi dòng tàu cảng: {e}")
                continue
                
        return {"message": "Import success", "imported": imported_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đọc file Excel: {str(e)}")


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
    others = scope3_other_vehicle_service.get_all_other_vehicle_records(db)
    items = sorted(
        [*containers, *others],
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

@router.delete("/api/scope3/ships/{ship_id}")
async def delete_ship_endpoint(ship_id: int, request: Request, db: Session = Depends(get_db)):
    return ship_service.delete_ship(ship_id, db, actor=_actor_from_request(request))


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

@router.delete("/api/scope3/harbor_crafts/{record_id}")
async def delete_harbor_craft(record_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        return harbor_craft_service.delete_harbor_craft(record_id, db, actor=_actor_from_request(request))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── COMBINED SUMMARY & AUDIT API ENDPOINTS ──────────────────

@router.get("/api/scope3/summary")
async def get_summary(db: Session = Depends(get_db)):
    """Get combined Scope 3 emissions summary"""
    container_summary = container_service.get_scope3_summary(db)
    
    ships = ship_service.get_all_ships(db)
    ship_total_co2 = sum(s.get("e_total", 0.0) if isinstance(s, dict) else getattr(s, "total_co2", getattr(s, "e_total", 0.0)) for s in ships)
    
    harbor_crafts = harbor_craft_service.get_all_harbor_crafts(db)
    harbor_total_co2 = sum(h.get("e_total", 0.0) for h in harbor_crafts)
    
    total_co2e = container_summary.get("total_co2", 0.0) + ship_total_co2 + harbor_total_co2
    total_trips = container_summary.get("total_trips", 0) + len(ships) + len(harbor_crafts)

    return {
        **container_summary,
        "container_co2e": container_summary.get("total_co2", 0.0),
        "ship_co2e": ship_total_co2,
        "harbor_co2e": harbor_total_co2,
        "total_co2e": total_co2e,
        "total_trips": total_trips
    }


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