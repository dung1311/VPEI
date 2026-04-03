from fastapi import APIRouter, Request, Depends, UploadFile, File, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import decode_token, get_token_payload
from services import electrical_items_service
from services import scope2_activity_service
from schemas.electrical_item import ElectricalItemCreate, ElectricalItemUpdate

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _actor_from_request(request: Request) -> str:
    payload = get_token_payload(request) or {}
    return payload.get("sub") or "system"

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
        "scope/scope_02_v2.html",
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

    history = scope2_activity_service.get_scope2_activity_history(db)

    return templates.TemplateResponse(
        "scope/scope_02_manager.html",
        {
            "request": request,
            "user": current_user,
            "audit_json": history["logs"],
            "available_years_json": history["available_years"],
            "can_delete": bool(current_user.get("is_admin")),
        },
    )

@router.post("/api/scope2/items")
async def create_electrical_item(item: ElectricalItemCreate, request: Request, db: Session = Depends(get_db)):
    return electrical_items_service.create_electrical_item(item, db, actor=_actor_from_request(request))


@router.get("/api/scope2/items")
async def list_electrical_items(db: Session = Depends(get_db)):
    return {"items": electrical_items_service.get_scope2_categories(db)}

@router.put("/api/scope2/items/{item_id}")
async def update_electrical_item(item_id: int, item: ElectricalItemUpdate, request: Request, db: Session = Depends(get_db)):
    return electrical_items_service.update_electrical_item(item_id, item, db, actor=_actor_from_request(request))

@router.delete("/api/scope2/items/{item_id}")
async def delete_electrical_item(item_id: int, request: Request, db: Session = Depends(get_db)):
    return electrical_items_service.delete_electrical_item(item_id, db, actor=_actor_from_request(request))


@router.post("/api/scope2/items/import-excel")
async def import_electrical_items_excel(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_bytes = await file.read()
    return electrical_items_service.import_scope2_items_from_excel(file_bytes, db, actor=_actor_from_request(request))


@router.get("/api/scope2/items/import-template-excel")
async def download_import_template_excel():
    payload = electrical_items_service.export_scope2_import_template_excel()
    return StreamingResponse(
        iter([payload]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scope2_import_template.xlsx"},
    )


@router.get("/api/scope2/items/export-excel")
async def export_electrical_items_excel(
    request: Request,
    mode: str | None = Query(default=None),
    bucket: str | None = Query(default=None),
    until_now: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    payload = electrical_items_service.export_scope2_items_excel(
        db,
        mode=mode,
        bucket=bucket,
        until_now=until_now,
        actor=_actor_from_request(request),
    )
    return StreamingResponse(
        iter([payload]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scope2_items.xlsx"},
    )


@router.get("/api/scope2/items/export-pdf")
async def export_electrical_items_pdf(
    request: Request,
    mode: str | None = Query(default=None),
    bucket: str | None = Query(default=None),
    until_now: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    payload = electrical_items_service.export_scope2_items_pdf(
        db,
        mode=mode,
        bucket=bucket,
        until_now=until_now,
        actor=_actor_from_request(request),
    )
    return StreamingResponse(
        iter([payload]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scope2_items.pdf"},
    )

@router.get("/api/scope2/manager/audit")
async def manager_audit_log(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    history = scope2_activity_service.get_scope2_activity_history(
        db, year=year, month=month, quarter=quarter
    )
    return history


@router.delete("/api/scope2/manager/audit/{activity_id}")
async def manager_delete_audit_log(
    activity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    payload = get_token_payload(request) or {}
    if not payload.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can delete activities",
        )
    return scope2_activity_service.delete_scope2_activity(db, activity_id)
