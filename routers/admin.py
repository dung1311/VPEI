from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.user import UserCreate
from core.security import require_admin
from services.user_service import UserService
from services.email_service import EmailService

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


def _ctx(request: Request, db: Session) -> tuple[dict, bool]:
    """Return (admin_payload, is_super_admin). Raises 302/403 if not admin."""
    admin = require_admin(request)
    return admin, bool(admin.get("is_super_admin"))


# ── GET /admin — user list ────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_home(request: Request, db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)
    users = UserService.get_all(db)
    return templates.TemplateResponse("admin/users.html", {
        "request":              request,
        "admin":                admin,
        "users":                users,
        "is_super_admin":       is_super,
        "flash":                request.query_params.get("flash"),
        "flash_type":           request.query_params.get("flash_type", "success"),
    })


# ── GET /admin/create ─────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
async def create_form(request: Request, db: Session = Depends(get_db)):
    _ctx(request, db)
    return templates.TemplateResponse("admin/create_user.html",
                                      {"request": request, "error": None})


# ── POST /admin/create ────────────────────────────────────────────────────────

@router.post("/create", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(default=""),
    password: str = Form(...),
    is_admin: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    _ctx(request, db)

    try:
        data = UserCreate(
            username=username, email=email,
            full_name=full_name, password=password, is_admin=is_admin,
        )
    except Exception as e:
        return templates.TemplateResponse("admin/create_user.html",
            {"request": request, "error": str(e)}, status_code=400)

    user, err = UserService.create(db, data)
    if err:
        return templates.TemplateResponse("admin/create_user.html",
            {"request": request, "error": err}, status_code=400)

    return RedirectResponse(
        url=f"{request.query_params.get('next', '/admin')}?flash=Tạo tài khoản '{user.username}' thành công.&flash_type=success",
        status_code=302)


# ── POST /admin/delete/{user_id} ──────────────────────────────────────────────

@router.post("/delete/{user_id}")
async def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)

    target = UserService.get_by_id(db, user_id)
    if not target:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash=Không tìm thấy user.&flash_type=error",
                                status_code=302)

    err = UserService.delete(db, target, admin["sub"], is_super)
    if err:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash={err}&flash_type=error", status_code=302)

    return RedirectResponse(
        url=f"{request.query_params.get('next', '/admin')}?flash=Đã xóa tài khoản '{target.username}'.&flash_type=success",
        status_code=302)


# ── GET /admin/reset/{user_id} ────────────────────────────────────────────────

@router.get("/reset/{user_id}", response_class=HTMLResponse)
async def reset_form(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)

    target = UserService.get_by_id(db, user_id)
    if not target:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash=Không tìm thấy user.&flash_type=error")

    # Check permission before rendering the form
    from services.user_service import UserService as US
    err = US._guard(target, admin["sub"], is_super, "reset mật khẩu")
    if err:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash={err}&flash_type=error", status_code=302)

    return templates.TemplateResponse("admin/reset_password.html",
        {"request": request, "user": target, "temp_password": None, "error": None})


# ── POST /admin/reset/{user_id} ───────────────────────────────────────────────

@router.post("/reset/{user_id}", response_class=HTMLResponse)
async def reset_password(
    user_id: int,
    request: Request,
    mode: str = Form(...),
    new_password: str = Form(default=""),
    send_email: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    admin, is_super = _ctx(request, db)

    target = UserService.get_by_id(db, user_id)
    if not target:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash=Không tìm thấy user.&flash_type=error")

    manual_pw = new_password.strip() if mode == "manual" else None
    if mode == "manual" and (not manual_pw or len(manual_pw) < 8):
        return templates.TemplateResponse("admin/reset_password.html",
            {"request": request, "user": target, "temp_password": None,
             "error": "Mật khẩu phải có ít nhất 8 ký tự."}, status_code=400)

    plain, err = UserService.reset_password(db, target, admin["sub"], is_super, manual_pw)
    if err:
        return templates.TemplateResponse("admin/reset_password.html",
            {"request": request, "user": target, "temp_password": None,
             "error": err}, status_code=403)

    # Send email notification if requested
    email_sent, email_error = False, None
    if send_email:
        ok, msg = EmailService.send_password_reset(
            to_email=target.email,
            full_name=target.full_name or "",
            username=target.username,
            temp_password=plain,
            reset_by=admin["sub"],
        )
        email_sent, email_error = ok, (None if ok else msg)

    return templates.TemplateResponse("admin/reset_password.html", {
        "request":           request,
        "user":              target,
        "temp_password":     plain,
        "error":             None,
        "email_sent":        email_sent,
        "email_error":       email_error,
        "send_email_checked": send_email,
    })


# ── POST /admin/toggle/{user_id} ──────────────────────────────────────────────

@router.post("/toggle/{user_id}")
async def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)

    target = UserService.get_by_id(db, user_id)
    if not target:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash=Không tìm thấy user.&flash_type=error",
                                status_code=302)

    user, err = UserService.toggle_active(db, target, admin["sub"], is_super)
    if err:
        return RedirectResponse(url=f"{request.query_params.get('next', '/admin')}?flash={err}&flash_type=error", status_code=302)

    label = "kích hoạt" if user.is_active else "khoá"
    return RedirectResponse(
        url=f"{request.query_params.get('next', '/admin')}?flash=Đã {label} tài khoản '{user.username}'.&flash_type=success",
        status_code=302)