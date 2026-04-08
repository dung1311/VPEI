import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from core.middleware import SessionValidationMiddleware
from routers import auth, dashboard, admin, scope1, scope2, scope3, settings, common, reports

app = FastAPI(title="VPEI – Vietnam Port Emission Inventory")
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

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})