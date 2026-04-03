from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import get_db
from core.security import create_access_token, decode_token, get_token_payload
from services.user_service import UserService

router = APIRouter()
templates = Jinja2Templates(directory="templates")
settings = get_settings()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = decode_token(token)
            if payload.get("sub"):
                return RedirectResponse(url="/dashboard", status_code=302)
        except Exception:
            pass
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember_me: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    user = UserService.authenticate(db, email, password)

    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Email hoặc mật khẩu không chính xác. Vui lòng thử lại."},
            status_code=401,
        )

    expire_minutes = (
        settings.access_token_expire_minutes * 24 * 7   # 7 days if remember
        if remember_me
        else settings.access_token_expire_minutes        # 60 min default
    )
    token = create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin},
        expires_delta=timedelta(minutes=expire_minutes),
    )

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,       # set True in production (HTTPS)
        samesite="lax",
        max_age=expire_minutes * 60,
    )
    return response


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user_info = getattr(request.state, "user", None)
    if not user_info or not user_info.get("sub"):
        return RedirectResponse(url="/login", status_code=302)

    username = user_info.get("sub")
    user = UserService.get_by_username_or_email(db, username)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
        
    return templates.TemplateResponse("auth/profile.html", {
        "request": request,
        "user_obj": user
    })


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

from fastapi.responses import JSONResponse
from core.security import verify_password, hash_password

@router.post("/api/auth/change-password")
async def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user_info = getattr(request.state, "user", None)
        if not user_info or not user_info.get("sub"):
            return JSONResponse(status_code=401, content={"status": "error", "message": "Chưa đăng nhập"})

        username = user_info.get("sub")
        user = UserService.get_by_username_or_email(db, username)
        if not user:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Không tìm thấy người dùng"})

        if not verify_password(old_password, user.hashed_password):
            return JSONResponse(status_code=400, content={"status": "error", "message": "Mật khẩu hiện tại không chính xác"})

        if len(new_password) < 8:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Mật khẩu mới phải có ít nhất 8 ký tự"})

        user.hashed_password = hash_password(new_password)
        db.commit()
        return JSONResponse(content={"status": "success", "message": "Cập nhật mật khẩu thành công"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})