from fastapi import APIRouter, Request, Depends, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import decode_token, get_token_payload
from services import container_service
from schemas.container import ContainerCreate, ContainerUpdate
from services import container_activity_service
from schemas.scope3_other_vehicle import Scope3OtherVehicleCreate
from services import scope3_other_vehicle_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _actor_from_request(request: Request) -> str:
    payload = get_token_payload(request) or {}
    return payload.get("sub") or "system"


@router.get("/scope3", response_class=HTMLResponse)
async def scope3_page(request: Request, db: Session = Depends(get_db)):
    """Render Scope 3 main page"""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    summary = container_service.get_scope3_summary(db)

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
    """Render Scope 3 manager/history page"""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = decode_token(token)
    except Exception:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie("access_token")
        return resp

    history = container_activity_service.get_scope3_activity_history(db)

    return templates.TemplateResponse(
        "scope/scope3_manager.html",
        {
            "request": request,
            "user": current_user,
            "audit_json": history["logs"],
            "available_years_json": history["available_years"],
            "can_delete": bool(current_user.get("is_admin")),
        },
    )


# ─── API ENDPOINTS ───────────────────────────────────────


@router.post("/api/scope3/containers")
async def create_container(
    container: ContainerCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create new container record"""
    return container_service.create_container(container, db, actor=_actor_from_request(request))


@router.get("/api/scope3/containers")
async def list_containers(db: Session = Depends(get_db)):
    """Get all Scope 3 records (containers + temporary other vehicles)"""
    containers = container_service.get_all_containers(db)
    others = scope3_other_vehicle_service.get_all_other_vehicle_records(db)
    items = sorted(
        [*containers, *others],
        key=lambda x: x.get("start_time") or x.get("created_at") or "",
        reverse=True,
    )
    return {"items": items, "count": len(items)}


@router.post("/api/scope3/other-vehicles")
async def create_other_vehicle_record(
    payload: Scope3OtherVehicleCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create temporary non-truck record for Scope 3 testing"""
    return scope3_other_vehicle_service.create_other_vehicle_record(
        payload,
        db,
        actor=_actor_from_request(request),
    )


@router.delete("/api/scope3/other-vehicles/{record_id}")
async def delete_other_vehicle_record(
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete temporary non-truck record"""
    return scope3_other_vehicle_service.delete_other_vehicle_record(
        record_id,
        db,
        actor=_actor_from_request(request),
    )


@router.get("/api/scope3/containers/{container_id}")
async def get_container(container_id: int, db: Session = Depends(get_db)):
    """Get specific container record"""
    return container_service.get_container_by_id(container_id, db)


@router.put("/api/scope3/containers/{container_id}")
async def update_container(
    container_id: int,
    container: ContainerUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update container record"""
    return container_service.update_container(
        container_id, container, db, actor=_actor_from_request(request)
    )


@router.delete("/api/scope3/containers/{container_id}")
async def delete_container(
    container_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete container record"""
    return container_service.delete_container(
        container_id, db, actor=_actor_from_request(request)
    )


@router.get("/api/scope3/summary")
async def get_summary(db: Session = Depends(get_db)):
    """Get Scope 3 emissions summary"""
    return container_service.get_scope3_summary(db)


@router.get("/api/scope3/manager/audit")
async def manager_audit_log(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get audit log for Scope 3"""
    history = container_activity_service.get_scope3_activity_history(db, year=year, month=month)
    return {
        "logs": history["logs"],
        "available_month_year": history["available_month_year"],
        "available_years": history["available_years"],
    }


@router.delete("/api/scope3/manager/audit/{activity_id}")
async def delete_audit_activity(
    activity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete audit activity (admin only)"""
    payload = get_token_payload(request) or {}
    if not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return container_activity_service.delete_scope3_activity(db, activity_id)
