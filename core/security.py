import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Request, status
from core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload.update({"exp": expire, "jti": str(uuid.uuid4())})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn.",
        )


# ── Auth guards ───────────────────────────────────────────────────────────────

def get_token_payload(request: Request) -> Optional[dict]:
    """Decode JWT from cookie. Returns None if missing or invalid."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return decode_token(token)
    except Exception:
        return None


def require_auth(request: Request) -> dict:
    """Redirect to /login if not authenticated."""
    payload = get_token_payload(request)
    if not payload:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return payload


def require_admin(request: Request) -> dict:
    """Redirect to /login if not authenticated, 403 if not admin."""
    payload = get_token_payload(request)
    if not payload:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if not payload.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập trang này.",
        )
    return payload