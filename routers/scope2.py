from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import decode_token
from services import electrical_items_service
from schemas.electrical_item import ElectricalItemCreate, ElectricalItemUpdate, ManagerRecordCreate

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/scope2", response_class=HTMLResponse)
async def scope2_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    categories = electrical_items_service.get_scope2_categories(db)

    return templates.TemplateResponse(
        "scope/scope_02.html",
        {
            "request": request,
            "user": current_user,
            "categories_json": categories
        }
    )


@router.get("/scope2/manager", response_class=HTMLResponse)
async def scope2_manager_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    devices = electrical_items_service.get_manager_devices(db)
    records = electrical_items_service.get_manager_records()
    audit = electrical_items_service.get_manager_audit()
    ef = electrical_items_service.get_ef()

    return templates.TemplateResponse(
        "scope/scope_02_manager.html",
        {
            "request": request,
            "user": current_user,
            "devices_json": devices,
            "records_json": records,
            "audit_json": audit,
            "ef": ef,
        },
    )

@router.post("/api/scope2/items")
async def create_electrical_item(item: ElectricalItemCreate, db: Session = Depends(get_db)):
    return electrical_items_service.create_electrical_item(item, db)

@router.put("/api/scope2/items/{item_id}")
async def update_electrical_item(item_id: int, item: ElectricalItemUpdate, db: Session = Depends(get_db)):
    return electrical_items_service.update_electrical_item(item_id, item, db)

@router.delete("/api/scope2/items/{item_id}")
async def delete_electrical_item(item_id: int, db: Session = Depends(get_db)):
    return electrical_items_service.delete_electrical_item(item_id, db)

@router.get("/api/scope2/manager/devices")
async def manager_devices(db: Session = Depends(get_db)):
    devices = electrical_items_service.get_manager_devices(db)
    return {"devices": devices}

@router.get("/api/scope2/manager/records")
async def manager_records():
    records = electrical_items_service.get_manager_records()
    return {"records": records}


@router.post("/api/scope2/manager/records")
async def manager_create_record(payload: ManagerRecordCreate):
    record = electrical_items_service.create_manager_record(payload)
    return {"ok": True, "record": record}


@router.delete("/api/scope2/manager/records/{record_id}")
async def manager_delete_record(record_id: int):
    return electrical_items_service.delete_manager_record(record_id)


@router.put("/api/scope2/manager/records/{record_id}")
async def manager_update_record(record_id: int, payload: ManagerRecordCreate):
    record = electrical_items_service.update_manager_record(record_id, payload)
    return {"ok": True, "record": record}


@router.post("/api/scope2/manager/upload-excel-mock")
async def manager_upload_excel_mock():
    return electrical_items_service.mock_upload_excel()

@router.get("/api/scope2/manager/audit")
async def manager_audit_log():
    audit = electrical_items_service.get_manager_audit()
    return {"logs": audit}
