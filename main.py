import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from core.middleware import SessionValidationMiddleware
from routers import auth, dashboard, admin, scope1_emission_source, frontend, scope1_dashboard

app = FastAPI(title="VPEI – Vietnam Port Emission Inventory")

# Validate session (is_active check) on every protected request
app.add_middleware(SessionValidationMiddleware)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(scope1_emission_source.router)
app.include_router(frontend.router)
app.include_router(scope1_dashboard.router)


@app.get("/")
async def root():
    return RedirectResponse(url="/login")