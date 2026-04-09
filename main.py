import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from core.middleware import SessionValidationMiddleware
from routers import auth, dashboard, admin, scope1, scope2, scope3, settings, common, reports

app = FastAPI(
    title="VPEI – Vietnam Port Emission Inventory",
    docs_url=None,
    redoc_url=None,
)
templates = Jinja2Templates(directory="templates")

# Validate session (is_active check) on every protected request
app.add_middleware(SessionValidationMiddleware)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

if os.path.isdir("templates/assets"):
    app.mount("/assets", StaticFiles(directory="templates/assets"), name="assets")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(settings.router)
app.include_router(scope1.router)
app.include_router(scope2.router)
app.include_router(scope3.router)
app.include_router(common.router)
app.include_router(reports.router)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return JSONResponse(status_code=exc.status_code,content={'detail': exc.detail})


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
