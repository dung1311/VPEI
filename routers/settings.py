from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import require_admin
from models.user import SUPER_ADMIN_USERNAME
from services.user_service import UserService

router = APIRouter(prefix="/settings", tags=["Settings"])
templates = Jinja2Templates(directory="templates")

def _ctx(request: Request, db: Session) -> tuple[dict, bool]:
    """Return (admin_payload, is_super_admin). Raises 302/403 if not admin."""
    admin = require_admin(request)
    return admin, admin.get("sub") == SUPER_ADMIN_USERNAME

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def settings_home(request: Request, db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)
    users = UserService.get_all(db)
    
    return templates.TemplateResponse("settings/settings.html", {
        "request": request,
        "admin": admin,
        "users": users,
        "is_super_admin": is_super,
        "super_admin_username": SUPER_ADMIN_USERNAME,
        "flash": request.query_params.get("flash"),
        "flash_type": request.query_params.get("flash_type", "success"),
    })

from fastapi import Body

@router.post("/api/users")
async def api_create_user(request: Request, data: dict = Body(...), db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)
    
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    full_name = data.get("full_name", "").strip()
    auto_password = data.get("auto_password", False)
    password = "" if auto_password else data.get("password", "")
    is_admin = data.get("is_admin", False)
    send_email = data.get("send_email", False)

    from schemas.user import UserCreate
    
    if auto_password:
        password = UserService._generate_password()
    
    try:
        user_data = UserCreate(
            username=username, email=email,
            full_name=full_name, password=password, is_admin=is_admin,
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

    user, err = UserService.create(db, user_data)
    if err:
        return {"status": "error", "message": err}

    if send_email:
        from services.email_service import EmailService
        ok, msg = EmailService.send_password_reset(
            to_email=user.email,
            full_name=user.full_name or "",
            username=user.username,
            temp_password=password,
            reset_by=admin["sub"],
        )
        if not ok:
            return {"status": "success", "message": f"Tạo tài khoản thành công nhưng gửi email lỗi: {msg}", "password": password if auto_password else None}

    return {"status": "success", "message": "Tạo tài khoản thành công.", "password": password if auto_password else None}

@router.post("/api/users/{user_id}/reset")
async def api_reset_password(user_id: int, request: Request, data: dict = Body(...), db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)

    auto_password = data.get("auto_password", False)
    manual_pw = "" if auto_password else data.get("new_password", "").strip()
    send_email = data.get("send_email", False)

    target = UserService.get_by_id(db, user_id)
    if not target:
        return {"status": "error", "message": "Không tìm thấy user."}

    if not auto_password and len(manual_pw) < 8:
        return {"status": "error", "message": "Mật khẩu phải có ít nhất 8 ký tự."}

    plain, err = UserService.reset_password(
        db, target, admin["sub"], is_super, 
        new_password=None if auto_password else manual_pw
    )
    
    if err:
        return {"status": "error", "message": err}

    if send_email:
        from services.email_service import EmailService
        ok, msg = EmailService.send_password_reset(
            to_email=target.email,
            full_name=target.full_name or "",
            username=target.username,
            temp_password=plain,
            reset_by=admin["sub"],
        )
        if not ok:
            return {"status": "success", "message": f"Reset thành công nhưng email lỗi: {msg}", "password": plain}

    return {"status": "success", "message": "Cấp lại mật khẩu thành công.", "password": plain}
