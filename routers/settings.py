from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import require_admin
from services.user_service import UserService

router = APIRouter(prefix="/settings", tags=["Settings"])
templates = Jinja2Templates(directory="templates")

def _ctx(request: Request, db: Session) -> tuple[dict, bool]:
    """Return (admin_payload, is_super_admin). Raises 302/403 if not admin."""
    admin = require_admin(request)
    return admin, bool(admin.get("is_super_admin"))

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def settings_home(request: Request, db: Session = Depends(get_db)):
    admin, is_super = _ctx(request, db)
    users = UserService.get_all(db)
    
    from models.settings import CompanySetting
    company_setting = db.query(CompanySetting).first()
    if not company_setting:
        company_setting = CompanySetting(company_name="Cảng VPEI – Việt Nam Port users = UserService.get_all(db) Energy Infrastructure", tax_code="0314852369", address="Số 1 Đường Cảng Biển, Khu kinh tế, TP. Hồ Chí Minh", logo_src="/static/company_logo_uploaded.png")
        db.add(company_setting)
        db.commit()
        db.refresh(company_setting)
    
    
    return templates.TemplateResponse("settings/settings.html", {
        "request": request,
        "admin": admin,
        "users": users,
        "is_super_admin": is_super,
        "company_setting": company_setting,
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

from fastapi import Form, File, UploadFile
import shutil
import os

@router.post("/api/company")
async def update_company_info(
    request: Request,
    company_name: str = Form(None),
    tax_code: str = Form(None),
    address: str = Form(None),
    logo_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    admin, is_super = _ctx(request, db)
    from models.settings import CompanySetting
    
    company_setting = db.query(CompanySetting).first()
    if not company_setting:
        company_setting = CompanySetting()
        db.add(company_setting)
        
    if company_name is not None:
        company_setting.company_name = company_name
    if tax_code is not None:
        company_setting.tax_code = tax_code
    if address is not None:
        company_setting.address = address
        
    if logo_file and logo_file.filename:
        os.makedirs("static", exist_ok=True)
        ext = os.path.splitext(logo_file.filename)[1]
        filename = f"company_logo_uploaded{ext}"
        filepath = os.path.join("static", filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(logo_file.file, buffer)
        company_setting.logo_src = f"/static/{filename}"
        
    db.commit()
    return {"status": "success", "message": "Cập nhật thành công."}
