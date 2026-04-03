"""
SessionValidationMiddleware

Runs on every non-public request:
  1. Decode JWT from HttpOnly cookie
  2. Check user still exists and is_active in DB

If either check fails → delete cookie + redirect /login immediately.
This ensures deleted or locked users are kicked out on next F5,
without waiting for the token to expire.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.database import SessionLocal
from models.user import User
from core.security import decode_token

PUBLIC_PATHS = {"/login", "/static"}


class SessionValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        token = request.cookies.get("access_token")

        if not token:
            if path not in ("/", "/favicon.ico"):
                return RedirectResponse(url="/login", status_code=302)
            return await call_next(request)

        try:
            payload = decode_token(token)
            request.state.user = payload
        except Exception:
            resp = RedirectResponse(url="/login", status_code=302)
            resp.delete_cookie("access_token")
            return resp

        username = payload.get("sub")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user or not user.is_active:
                resp = RedirectResponse(url="/login", status_code=302)
                resp.delete_cookie("access_token")
                return resp
        finally:
            db.close()

        return await call_next(request)